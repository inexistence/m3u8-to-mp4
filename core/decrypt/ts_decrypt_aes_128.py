"""AES-128 CBC 解密，自动兼容两种常见的 HLS 分片加密格式。

不同下载源对同一 m3u8 标准的实现方式不同，本项目通过解密结果的 TS 特征评分自动选择模式：

1. prepended（前置 IV）
   - 分片文件的前 16 字节密文作为 CBC 的 IV，剩余部分为密文
   - 常见于部分国内下载器（如迅雷等），解密后可能带有 FFmpeg 元数据头，TS 同步字节不一定在 offset 0

2. hls（标准 HLS IV）
   - 整个分片文件都是密文
   - IV 来自 m3u8 的 #EXT-X-KEY:IV= 属性；若未声明则使用分片序号（#EXT-X-MEDIA-SEQUENCE + 偏移）
   - 解密后 TS 同步字节 0x47 通常位于文件开头

首个加密分片会尝试上述两种模式并比较评分，选定后缓存模式供后续分片复用。
也可通过 config.yaml 的 aes_iv_mode 指定 prepended / hls，未配置或为 auto 时走自动检测。
"""
from core.decrypt.ts_decrypt import TsDecrypt
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from tqdm import tqdm

TS_PACKET_SIZE = 188
# MPEG-TS 同步字节（ISO/IEC 13818-1 规定）
# 每个 TS 包固定 188 字节，首字节必须是 0x47，用于在字节流中定位包边界。
# 0x47 的位模式（01000111）在普通音视频载荷中极少连续出现，误判率低，适合作为同步标记。
TS_SYNC_BYTE = 0x47
# prepended 模式评分达到此阈值即视为有效，不再尝试 hls 模式
MIN_PREPENDED_TS_SCORE = 3


def ts_validity_score(data: bytes) -> int:
    """评估解密结果是否像合法的 MPEG-TS 流，分数越高越可信。

    MPEG-TS 以 188 字节为一个包，每个包的第一个字节必须是同步字节 0x47。
    解密正确时，数据流中应能周期性（每隔 188 字节）找到 0x47；若找不到或间隔错乱，
    说明 IV 模式可能不对。部分下载源解密后会在 TS 流前附加自定义头，因此在 0~187
    的偏移范围内寻找最佳对齐点，统计连续匹配的包数量作为评分。
    """
    if len(data) < TS_PACKET_SIZE:
        return 0

    best = 0
    scan_limit = min(TS_PACKET_SIZE, len(data))
    for offset in range(scan_limit):
        if data[offset] != TS_SYNC_BYTE:
            continue

        score = 1
        for i in range(1, min(10, (len(data) - offset) // TS_PACKET_SIZE)):
            if data[offset + i * TS_PACKET_SIZE] == TS_SYNC_BYTE:
                score += 1
            else:
                break

        # TS 从文件头开始时额外加分，优先选择更标准的布局
        if offset == 0:
            score += 2

        best = max(best, score)

    return best


class TsDecrypt_AES128_CBC(TsDecrypt):
    MODE_AUTO = 'auto'
    MODE_PREPENDED = 'prepended'  # 前 16 字节密文作为 IV
    MODE_HLS = 'hls'              # 标准 HLS：整段密文 + 序号/声明 IV
    VALID_MODES = {MODE_AUTO, MODE_PREPENDED, MODE_HLS}

    def __init__(self, key: str | bytes, iv: bytes | str | None = None, iv_mode: str = MODE_AUTO):
        if isinstance(key, str):
            self.key = key.encode('utf-8')
        elif isinstance(key, bytes):
            self.key = key

        # m3u8 中 #EXT-X-KEY 声明的 IV（可选），仅 hls 模式使用
        if isinstance(iv, str):
            iv = iv.strip('0x')
            self.iv = bytes.fromhex(iv)
        else:
            self.iv = iv

        if iv_mode not in self.VALID_MODES:
            tqdm.write(f'unknown aes_iv_mode "{iv_mode}", fallback to auto')
            iv_mode = self.MODE_AUTO
        self._iv_mode = iv_mode

        self._cached_mode: str | None = None       # 首个分片检测后缓存，避免重复尝试
        self._key_start_sequence = 0               # 当前 key 生效时的分片序号，用于 IV 递增

    def set_key_start_sequence(self, sequence: int):
        """记录 #EXT-X-KEY 标签出现时对应的分片序号，换 key 后需重新检测模式。"""
        self._key_start_sequence = sequence
        self._cached_mode = None

    def reset_detect_mode(self):
        """DISCONTINUITY 等场景重置解密器时，清除已缓存的解密模式。"""
        self._cached_mode = None

    def _decrypt_cbc(self, ciphertext: bytes, iv: bytes) -> bytes:
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        decrypted_data_padded = cipher.decrypt(ciphertext)
        try:
            return unpad(decrypted_data_padded, AES.block_size)
        except Exception:
            # 部分分片填充不规范，保留去填充前的数据交给 FFmpeg 处理
            return decrypted_data_padded

    def _hls_iv(self, sequence_number: int) -> bytes:
        """按 HLS 规范计算 IV：有声明则从声明值起按分片序号递增，否则直接用分片序号。"""
        if self.iv is not None:
            base = int.from_bytes(self.iv, byteorder='big')
            value = base + (sequence_number - self._key_start_sequence)
        else:
            value = sequence_number
        return value.to_bytes(16, byteorder='big')

    def _decrypt_prepended(self, data: bytes) -> bytes:
        """前置 IV 模式：分片头部 16 字节为 IV，后续为密文。"""
        iv = data[:AES.block_size]
        ciphertext = data[AES.block_size:]
        return self._decrypt_cbc(ciphertext, iv)

    def _decrypt_hls(self, data: bytes, sequence_number: int) -> bytes:
        """标准 HLS 模式：整段分片为密文，IV 由分片序号或 m3u8 声明值决定。"""
        return self._decrypt_cbc(data, self._hls_iv(sequence_number))

    def _decrypt_with_mode(self, data: bytes, sequence_number: int, mode: str) -> bytes:
        if mode == self.MODE_PREPENDED:
            return self._decrypt_prepended(data)
        return self._decrypt_hls(data, sequence_number)

    def _detect_mode(self, data: bytes, sequence_number: int) -> str:
        """对首个分片检测解密模式。优先尝试 prepended，足够好则跳过后续尝试。"""
        prepended_result = self._decrypt_prepended(data)
        prepended_score = ts_validity_score(prepended_result)
        if prepended_score >= MIN_PREPENDED_TS_SCORE:
            return self.MODE_PREPENDED

        hls_result = self._decrypt_hls(data, sequence_number)
        hls_score = ts_validity_score(hls_result)
        if hls_score > prepended_score:
            return self.MODE_HLS

        return self.MODE_PREPENDED

    def decrypt(self, data, sequence_number: int = 0):
        if self._cached_mode is None:
            if self._iv_mode != self.MODE_AUTO:
                self._cached_mode = self._iv_mode
                tqdm.write(f'aes-128 decrypt mode: {self._cached_mode} (config)')
            else:
                self._cached_mode = self._detect_mode(data, sequence_number)
                tqdm.write(f'aes-128 decrypt mode: {self._cached_mode} (auto)')

        return self._decrypt_with_mode(data, sequence_number, self._cached_mode)
