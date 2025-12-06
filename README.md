[下载 ffmpeg](https://ffmpeg.org/download.html) 并将 bin 文件夹设置到环境变量


创建虚拟环境

```shell
python -m venv .venv
```

### Windows PowerShell

应用虚拟环境

```shell
.\.venv\Scripts\Activate.ps1
```

如果提示没有权限，则可以执行

```shell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

安装依赖

```shell
pip install -r requirements.txt
```

执行任务，文件路径设为最外层的 m3u8 文件路径，最终结果将生成在 index.m3u8 所在文件夹下

```shell
python .\main.py 'file path'
```

保存依赖

```shell
pip freeze > requirements.txt
```

### 依赖库
ffmpeg-python：用于ts视频合并
pycryptodome：用于解密