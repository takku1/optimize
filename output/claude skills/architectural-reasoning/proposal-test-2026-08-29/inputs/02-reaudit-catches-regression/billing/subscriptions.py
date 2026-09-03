def cancel_subscription(sub_id):
    with db.transaction():
        sub = db.query(Subscription).filter_by(id=sub_id).with_for_update().one()
        sub.status = "canceled"
        db.commit()
    # refund moved outside the transaction, per the prior audit's recommendation
    stripe_client.refund(sub.charge_id)
    return sub
