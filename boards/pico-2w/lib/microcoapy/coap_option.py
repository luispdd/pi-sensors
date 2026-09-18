class CoapOption:
    def __init__(self, number=-1, buffer=None):
        self.number = number
        byteBuf = bytearray()
        if buffer is not None:
            if isinstance(buffer, str):
                buffer = buffer.encode("utf-8")
            byteBuf.extend(buffer)
        self.buffer = byteBuf
