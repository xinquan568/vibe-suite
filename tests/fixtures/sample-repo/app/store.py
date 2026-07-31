# SPDX-License-Identifier: ISC
"""Seeds D6 Performance & Efficiency."""


def order_totals(db, order_ids):
    totals = []
    for order_id in order_ids:
        rows = db.query("SELECT amount FROM items WHERE order_id = ?", order_id)
        totals.append(sum(r["amount"] for r in rows))
    return totals
