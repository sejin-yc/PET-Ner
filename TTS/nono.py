from cosyvoice.tokenizer.tokenizer import get_qwen_tokenizer
tok = get_qwen_tokenizer("모델경로/CosyVoice-BlankEN", skip_special_tokens=True, version="cosyvoice3")
t = "저는 요새 사람들을 좀 만나고 있어요."
ids = tok.encode(t, allowed_special="all")  # 실제 frontend에서 쓰는 형태에 맞게
print(len(t), "자 →", len(ids), "토큰")