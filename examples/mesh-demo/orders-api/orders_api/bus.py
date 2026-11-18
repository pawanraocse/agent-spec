class _Producer:
    def send(self, topic, message):
        print(topic, message)


producer = _Producer()
