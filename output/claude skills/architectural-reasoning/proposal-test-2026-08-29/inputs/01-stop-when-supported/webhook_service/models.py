class Webhook(Base):
    __tablename__ = "webhooks"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    # no timeout field yet
