def enable_os_truststore() -> bool:
    """Windows/사내망 SSL 검사 대응: OS 인증서 저장소를 Python SSL에 주입."""
    try:
        import truststore
        truststore.inject_into_ssl()
        return True
    except Exception:
        return False
