from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import subprocess
import tempfile
import os
import shutil

# 让静态根就是当前目录，便于 Demo.html 引用本地资源
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

VOICES_DIR = r"D:\Wolfe\WorkDemo\LiveTalking2-Wav2lip\piper\voice-zh_CN-huayan-medium"

def list_voices():
    voices = []
    if os.path.isdir(VOICES_DIR):
        for f in os.listdir(VOICES_DIR):
            if f.lower().endswith('.onnx'):
                voices.append(os.path.splitext(f)[0])
    return voices

@app.get("/")
def index():
    """主页：返回前端页面"""
    # 如果 Demo.html 和 app.py 同目录
    return send_file("Demo.html")

@app.get("/voices")
def voices():
    """返回可用的语音模型 ID 列表（文件名去后缀）"""
    return jsonify(list_voices())

@app.post("/speak")
def speak():
    """TTS 合成：接收 JSON，调用 piper 生成 wav 并返回"""
    data = request.get_json(force=True) or {}
    text = data.get("text", "").strip()
    voice = (data.get("voice") or "").strip()
    length_scale = float(data.get("length_scale", 1.0))
    noise_scale = float(data.get("noise_scale", 0.667))
    noise_w_scale = float(data.get("noise_w_scale", 0.8))

    if not text:
        return jsonify({"error": "text is empty"}), 400
    if not voice:
        return jsonify({"error": "voice is required"}), 400

    model_path = os.path.join(VOICES_DIR, voice + ".onnx")
    if not os.path.isfile(model_path):
        return jsonify({"error": f"model not found: {model_path}"}), 404

    # 确认 piper 可执行是否可用（Windows 安装为 piper 或 piper.exe）
    piper_bin = shutil.which("piper") or shutil.which("piper.exe")
    if not piper_bin:
        return jsonify({"error": "piper executable not found in PATH"}), 500

    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name

        cmd = [
            piper_bin,
            "--model", model_path,
            "--length_scale", str(length_scale),
            "--noise_scale", str(noise_scale),
            "--noise_w_scale", str(noise_w_scale),
            "--output_file", tmp_name,
        ]

        # 向 piper 的 stdin 写入文本（Windows 可行）
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if proc.returncode != 0 or not os.path.exists(tmp_name) or os.path.getsize(tmp_name) == 0:
            return jsonify({
                "error": "piper failed",
                "stderr": proc.stderr.decode("utf-8", errors="ignore")
            }), 500

        return send_file(tmp_name, mimetype="audio/wav")

    finally:
        # 注意：send_file 结束后文件仍被占用的情况较少见，如遇到可延迟删除或改为临时目录轮询清理
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except Exception:
                pass

if __name__ == "__main__":
    # 明确 host/port，关闭 debug 以减少控制台噪声
    app.run(host="127.0.0.1", port=5000, debug=False)
