    def show_invoice(self, order_id):
        with database() as con:
            order = con.execute(
                """SELECT o.id,o.title,o.total,o.paid,o.date,c.name,c.phone
                   FROM orders o LEFT JOIN customers c ON c.id=o.customer_id
                   WHERE o.id=?""",
                (order_id,)
            ).fetchone()
            items = con.execute(
                """SELECT product_name,category,quantity,unit_price,line_total
                   FROM order_items WHERE order_id=? ORDER BY id""",
                (order_id,)
            ).fetchall()

        if not order:
            return

        oid, title, total, paid, date, customer, phone = order
        lines = [
            "شماره فاکتور: {}".format(oid),
            "تاریخ: {}".format(date),
            "مشتری: {}".format(customer or "-"),
            "تلفن: {}".format(phone or "-"),
            "",
            "اقلام:"
        ]

        for name, category, qty, price, line_total in items:
            lines.append("{} ({}) | {} × {} = {}".format(
                name, category, qty, money(price), money(line_total)
            ))

        lines.extend([
            "",
            "جمع کل: {} تومان".format(money(total)),
            "پرداختی: {} تومان".format(money(paid)),
            "مانده: {} تومان".format(money(total - paid))
        ])

        content = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(6)
        )
        details = Label(
            text=fa("\n".join(lines)),
            font_name="Vazir",
            font_size="13sp",
            color=DARK,
            halign="right",
            valign="top"
        )
        content.add_widget(details)

        popup = Popup(
            title=fa("فاکتور فروش"),
            content=content,
            size_hint=(0.92, 0.82)
        )
        content.add_widget(button(
            "بستن",
            lambda *_: popup.dismiss(),
            height=40
        ))
        popup.open()
