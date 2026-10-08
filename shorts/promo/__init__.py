"""모션 그래픽 제품 소개 영상(가로 1920x1080) 생성 모듈.

브라우저(HTML/CSS/JS)로 한 프레임씩 그려 ffmpeg으로 묶는다. 전부 무료 도구만 쓴다.
"""
from .spec import PromoScript, Scene, SceneValidationError

__all__ = ["PromoScript", "Scene", "SceneValidationError"]
