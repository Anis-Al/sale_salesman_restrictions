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
