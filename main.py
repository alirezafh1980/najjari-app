    def save_product(self, *_):
        name = self.name_input.text.strip()
        category = self.categories.get(self.category_spinner.text)
        price = parse_number(self.price_input.text)
        produced = parse_number(self.stock_input.text)

        if not name or not category or price < 0 or produced < 0:
            message("نام، دسته، قیمت و مقدار تولید معتبر وارد کنید")
            return

        selected = self.products.get(self.product_spinner.text)

        with database() as con:
            if selected:
                con.execute(
                    "UPDATE products "
                    "SET name=?, category=?, price=?, stock=stock+? "
                    "WHERE id=?",
                    (name, category, price, produced, selected[0])
                )
            else:
                con.execute(
                    "INSERT INTO products(name,category,price,stock) "
                    "VALUES(?,?,?,?)",
                    (name, category, price, produced)
                )

        self.clear_form()
        self.refresh()
