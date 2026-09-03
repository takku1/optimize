class BillingService:
    def charge(self, invoice):
        conn = db.connect()
        row = conn.execute("SELECT * FROM invoices WHERE id=?", invoice.id).fetchone()
        result = stripe_client.charge(row["amount"], row["customer_id"])
        conn.execute("UPDATE invoices SET status=? WHERE id=?", ("charged", invoice.id))
        return result
