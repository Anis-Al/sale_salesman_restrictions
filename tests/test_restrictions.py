from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSalesmanRestrictions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = 'sales_team.group_sale_salesman,sale.group_discount_per_so_line'
        cls.salesman = new_test_user(cls.env, 'salesman_test', groups=groups)
        cls.manager = new_test_user(cls.env, 'manager_test', groups=groups + ',sales_team.group_sale_manager')
        cls.partner = cls.env['res.partner'].create({'name': "Client"})
        cls.product = cls.env['product.product'].create({'name': "Chair", 'list_price': 100.0})
        cls.pricelist = cls.env['product.pricelist'].create({'name': "No rules"})
        cls.env.company.sale_discount_product_id = cls.env['product.product'].create({
            'name': "Discount", 'type': 'service',
        })

    def _order(self, user):
        return self.env['sale.order'].with_user(user).create({
            'partner_id': self.partner.id,
            'pricelist_id': self.pricelist.id,
            'order_line': [(0, 0, {'product_id': self.product.id})],
        })

    def test_line_discount(self):
        line = self._order(self.salesman).order_line
        line.discount = 5.0
        with self.assertRaises(ValidationError):
            line.discount = 5.5
        self._order(self.manager).order_line.discount = 50.0

    def test_configurable_cap(self):
        self.env.company.salesman_max_discount = 10.0
        line = self._order(self.salesman).order_line
        line.discount = 10.0
        with self.assertRaises(ValidationError):
            line.discount = 10.5
        Wizard = self.env['sale.order.discount'].with_user(self.salesman)
        Wizard.create({'sale_order_id': line.order_id.id, 'discount_type': 'sol_discount', 'discount_percentage': 0.1})
        with self.assertRaises(ValidationError):
            Wizard.create({'sale_order_id': line.order_id.id, 'discount_type': 'sol_discount', 'discount_percentage': 0.11})

    def test_wizard(self):
        order = self._order(self.salesman)
        Wizard = self.env['sale.order.discount'].with_user(self.salesman)
        for vals in (
            {'discount_type': 'sol_discount', 'discount_percentage': 0.06},
            {'discount_type': 'so_discount', 'discount_percentage': 0.06},
            {'discount_type': 'amount', 'discount_amount': 1.0},
        ):
            with self.assertRaises(ValidationError):
                Wizard.create({'sale_order_id': order.id, **vals})
        Wizard.create({
            'sale_order_id': order.id, 'discount_type': 'sol_discount', 'discount_percentage': 0.05,
        }).action_apply_discount()
        self.assertEqual(order.order_line.discount, 5.0)

        def types(user):
            return [s[0] for s in Wizard.with_user(user).fields_get(['discount_type'])['discount_type']['selection']]
        self.assertNotIn('amount', types(self.salesman))
        self.assertIn('amount', types(self.manager))

    def test_global_discount_line_qty(self):
        order = self._order(self.salesman)
        self.env['sale.order.discount'].with_user(self.salesman).create({
            'sale_order_id': order.id, 'discount_type': 'so_discount', 'discount_percentage': 0.05,
        }).action_apply_discount()
        line = order.order_line.filtered(lambda l: l.product_id == self.env.company.sale_discount_product_id)
        self.assertEqual(len(line), 1)
        qty = line.product_uom_qty
        with self.assertRaises(ValidationError):
            line.with_user(self.salesman).product_uom_qty = qty + 1
        line.with_user(self.salesman).product_uom_qty = qty
        line.with_user(self.manager).product_uom_qty = qty + 1

    def test_invoice_taxes_hidden(self):
        def has_taxes(user):
            arch = self.env['account.move'].with_user(user).get_views([(False, 'form')])['views']['form']['arch']
            return 'name="tax_ids"' in arch
        self.assertFalse(has_taxes(self.salesman))
        self.assertTrue(has_taxes(self.manager))
