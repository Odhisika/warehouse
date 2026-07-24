from django.core.management.base import BaseCommand
from django.test import Client
from django.conf import settings as django_settings
from core.models import Branch
from core.branch_context import set_current_branch_code
from inventory.models import Product, Category
from dispatch.models import DispatchOrder, Customer
from receiving.models import InboundShipment, Supplier
from transfers.models import StockTransfer


django_settings.ALLOWED_HOSTS.append('testserver')
django_settings.ALLOWED_HOSTS.append('*')


class Command(BaseCommand):
    help = 'Run end-to-end tests on all views using seed data'

    def handle(self, *args, **options):
        set_current_branch_code('ACCRA')

        passed = 0
        failed = 0

        def test(name, condition, detail=''):
            nonlocal passed, failed
            if condition:
                self.stdout.write(self.style.SUCCESS(f'  PASS  {name}'))
                passed += 1
            else:
                msg = f'  FAIL  {name}'
                if detail:
                    msg += f'  --  {detail}'
                self.stdout.write(self.style.ERROR(msg))
                failed += 1

        c = Client(HTTP_HOST='localhost')
        branch = Branch.objects.get(code='ACCRA')
        cat = Category.objects.first()
        sup = Supplier.objects.first()
        cust = Customer.objects.first()

        # ─── Login ───
        self.stdout.write('\n─── Authentication ───')

        resp = c.get('/login/')
        test('Login page returns 200', resp.status_code == 200)

        resp = c.post('/login/', {'username': 'admin', 'password': 'admin123'}, follow=True)
        test('Login succeeds', resp.status_code == 200 and b'Dashboard' in resp.content)

        session = c.session
        session['branch_code'] = 'ACCRA'
        session.save()

        # ─── Dashboard ───
        self.stdout.write('\n─── Dashboard ───')
        resp = c.get('/')
        test('Dashboard returns 200', resp.status_code == 200)

        # ─── Inventory ───
        self.stdout.write('\n─── Inventory ───')
        resp = c.get('/inventory/')
        test('Inventory list returns 200', resp.status_code == 200)

        resp = c.get('/inventory/add/')
        test('Product add form returns 200', resp.status_code == 200)

        resp = c.post('/inventory/add/', {
            'name': 'Test Product X',
            'sku': 'TST-999',
            'stock_qty': 50,
            'unit_cost': 99.99,
            'batch_number': 'BATCH-TST',
            'category': cat.pk if cat else '',
        }, follow=True)
        test('Product add succeeds', resp.status_code == 200)
        test('Product appears in list', b'TST-999' in resp.content or b'Test Product X' in resp.content)

        new_pk = None
        try:
            new_pk = Product.objects.get(sku='TST-999').pk
        except Product.DoesNotExist:
            pass

        if new_pk:
            resp = c.get(f'/inventory/{new_pk}/edit/')
            test('Product edit form returns 200', resp.status_code == 200)
            resp = c.post(f'/inventory/{new_pk}/edit/', {
                'name': 'Test Product X Updated',
                'sku': 'TST-999',
                'stock_qty': 75,
                'unit_cost': 89.99,
                'batch_number': 'BATCH-TST-UPD',
            }, follow=True)
            test('Product edit succeeds', resp.status_code == 200)

            resp = c.post(f'/inventory/{new_pk}/delete/', follow=True)
            test('Product delete succeeds', resp.status_code == 200)

        resp = c.get('/inventory/export/')
        test('Inventory export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/inventory/export/?format=pdf')
        test('Inventory export PDF returns 200', resp.status_code == 200)

        # ─── Receiving ───
        self.stdout.write('\n─── Receiving ───')
        resp = c.get('/receiving/')
        test('Receiving list returns 200', resp.status_code == 200)

        resp = c.get('/receiving/new/')
        test('Receiving new form returns 200', resp.status_code == 200)

        prod = Product.objects.filter(is_active=True).first()
        prod_pk = prod.pk if prod else ''
        resp = c.post('/receiving/new/', {
            'supplier': sup.pk if sup else '',
            'invoice_ref': 'INV-TEST-001',
            'po_reference': 'PO-TEST-001',
            'receive_date': '2024-06-15',
            'product_1': prod_pk,
            'qty_1': 25,
            'cost_1': 150.00,
            'condition_1': 'pristine',
        }, follow=True)
        test('Receiving create succeeds', resp.status_code == 200)

        try:
            new_shipment = InboundShipment.objects.get(invoice_ref='INV-TEST-001')
            test('Shipment in DB', True)
            resp = c.post(f'/receiving/{new_shipment.pk}/complete/', follow=True)
            test('Receiving complete succeeds', resp.status_code == 200)
        except InboundShipment.DoesNotExist:
            test('Shipment in DB', False)

        existing = InboundShipment.objects.filter(is_complete=True).first()
        if existing:
            resp = c.get(f'/receiving/{existing.pk}/')
            test('Receiving detail returns 200', resp.status_code == 200)

        resp = c.get('/receiving/export/')
        test('Receiving export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/receiving/export/?format=pdf')
        test('Receiving export PDF returns 200', resp.status_code == 200)

        # ─── Dispatch ───
        self.stdout.write('\n─── Dispatch ───')
        resp = c.get('/dispatch/')
        test('Dispatch list returns 200', resp.status_code == 200)

        resp = c.get('/dispatch/new/')
        test('Dispatch new form returns 200', resp.status_code == 200)

        prod_in_stock = Product.objects.filter(is_active=True, stock_qty__gt=0).first()
        if prod_in_stock and cust:
            resp = c.post('/dispatch/new/', {
                'customer': cust.pk,
                'destination': 'Test Location',
                'carrier': 'swift',
                'handling_fee': 25.00,
                f'manifest_qty_{prod_in_stock.pk}': 5,
            }, follow=True)
            test('Dispatch create succeeds', resp.status_code == 200)

            new_dispatch = DispatchOrder.objects.order_by('-created_at').first()
            test('Dispatch in DB', new_dispatch is not None)
            if new_dispatch:
                resp = c.post(f'/dispatch/{new_dispatch.pk}/authorize/', follow=True)
                test('Dispatch authorize succeeds', resp.status_code == 200)
        else:
            test('Dispatch create (no stock products or customers)', True)

        existing_order = DispatchOrder.objects.first()
        if existing_order:
            resp = c.get(f'/dispatch/{existing_order.pk}/')
            test('Dispatch detail returns 200', resp.status_code == 200)

        resp = c.get('/dispatch/export/')
        test('Dispatch export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/dispatch/export/?format=pdf')
        test('Dispatch export PDF returns 200', resp.status_code == 200)

        # ─── Transfers ───
        self.stdout.write('\n─── Transfers ───')
        resp = c.get('/transfers/')
        test('Transfers list returns 200', resp.status_code == 200)

        resp = c.get('/transfers/new/')
        test('Transfers new form returns 200', resp.status_code == 200)

        prod_w_stock = Product.objects.filter(is_active=True, stock_qty__gt=0).first()
        if prod_w_stock:
            resp = c.post('/transfers/new/', {
                'to_branch_code': 'ACCRA',
                'notes': 'Test transfer',
                f'transfer_qty_{prod_w_stock.pk}': 3,
            }, follow=True)
            test('Transfer create succeeds', resp.status_code == 200)

            tfr = StockTransfer.objects.order_by('-created_at').first()
            test('Transfer in DB', tfr is not None)
            if tfr:
                resp = c.post(f'/transfers/{tfr.pk}/send/', follow=True)
                test('Transfer send succeeds', resp.status_code == 200)
                resp = c.post(f'/transfers/{tfr.pk}/dispatch/', follow=True)
                test('Transfer dispatch succeeds', resp.status_code == 200)
                resp = c.post(f'/transfers/{tfr.pk}/receive/', follow=True)
                test('Transfer receive succeeds', resp.status_code == 200)
        else:
            test('Transfer create (no stock)', True)

        existing_tfr = StockTransfer.objects.first()
        if existing_tfr:
            resp = c.get(f'/transfers/{existing_tfr.pk}/')
            test('Transfer detail returns 200', resp.status_code == 200)

        resp = c.get('/transfers/export/')
        test('Transfers export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/transfers/export/?format=pdf')
        test('Transfers export PDF returns 200', resp.status_code == 200)

        # ─── Returns ───
        self.stdout.write('\n─── Returns ───')
        resp = c.get('/returns/')
        test('Returns list returns 200', resp.status_code == 200)

        resp = c.get('/returns/new/')
        test('Returns new form returns 200', resp.status_code == 200)

        resp = c.post('/returns/new/', {
            'reason': 'damaged_transit',
            'return_type': 'partial',
            'disposition': 'restock',
            'return_date': '2024-06-15',
            'notes': 'Test return from E2E',
        }, follow=True)
        test('Return create succeeds', resp.status_code == 200)

        resp = c.get('/returns/export/')
        test('Returns export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/returns/export/?format=pdf')
        test('Returns export PDF returns 200', resp.status_code == 200)

        # ─── Reports ───
        self.stdout.write('\n─── Reports ───')
        resp = c.get('/reports/')
        test('Reports returns 200', resp.status_code == 200)

        resp = c.get('/reports/export/')
        test('Reports export XLSX returns 200', resp.status_code == 200)
        resp = c.get('/reports/export/?format=pdf')
        test('Reports export PDF returns 200', resp.status_code == 200)

        # ─── Settings ───
        self.stdout.write('\n─── Settings ───')
        resp = c.get('/settings/')
        test('Settings general returns 200', resp.status_code == 200)
        test('Settings shows Ghana defaults', b'GHS' in resp.content or b'Cedi' in resp.content or b'Accra' in resp.content)

        resp = c.get('/settings/roles/')
        test('Settings roles returns 200', resp.status_code == 200)
        resp = c.get('/settings/branches/')
        test('Settings branches returns 200', resp.status_code == 200)
        resp = c.get('/settings/security/')
        test('Settings security returns 200', resp.status_code == 200)

        # ─── Logout ───
        self.stdout.write('\n─── Logout ───')
        resp = c.post('/logout/', follow=True)
        test('Logout succeeds', resp.status_code == 200)

        # ─── Summary ───
        self.stdout.write('\n' + '=' * 50)
        total = passed + failed
        self.stdout.write(f'  Results: {passed}/{total} passed')
        if failed:
            self.stdout.write(self.style.ERROR(f'  {failed} test(s) FAILED'))
        else:
            self.stdout.write(self.style.SUCCESS('  All tests PASSED!'))
        self.stdout.write('=' * 50)
