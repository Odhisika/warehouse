from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.contrib.auth.models import User
from django.db import connection
from core.models import Branch, SiteSettings, SystemAlert, UserProfile
from core.branch_context import set_current_branch_code
from core.db_router import register_branch_db


class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')
        branch_code = 'ACCRA'
        branch_name = 'Accra Main Branch'

        # --- Default DB data (core models) ---
        branch, created = Branch.objects.get_or_create(
            code=branch_code,
            defaults={
                'name': branch_name,
                'location': 'Accra, Ghana',
                'manager': 'John D.',
                'capacity_percent': 72,
                'status': 'active',
                'region': 'Greater Accra',
            },
        )
        if created:
            self.stdout.write(f'  Created branch: {branch_name} ({branch_code})')
        else:
            self.stdout.write(f'  Branch exists: {branch_name} ({branch_code})')

        # Run migrations on branch DB
        register_branch_db(branch_code)
        call_command('migrate', database=f'branch_{branch_code}', interactive=False, verbosity=0)
        self.stdout.write('  Migrated branch database')

        # Superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write('  Created superuser: admin / admin123')
        else:
            self.stdout.write('  Superuser admin already exists')

        # Regular user
        if not User.objects.filter(username='warehouse1').exists():
            u = User.objects.create_user('warehouse1', 'w1@example.com', 'pass123', first_name='Kwame', last_name='Asante')
            UserProfile.objects.get_or_create(user=u, defaults={'is_global_admin': False})
            self.stdout.write('  Created user: warehouse1 / pass123')
        else:
            self.stdout.write('  User warehouse1 already exists')

        # Assign branch access
        for username in ('admin', 'warehouse1'):
            try:
                u = User.objects.get(username=username)
                profile, _ = UserProfile.objects.get_or_create(user=u)
                profile.allowed_branches.add(branch)
            except User.DoesNotExist:
                pass
        self.stdout.write('  Assigned branch access')

        # System Alerts
        if not SystemAlert.objects.exists():
            SystemAlert.objects.create(
                title='Inventory Audit Required',
                description='End-of-month stock count is pending for Accra warehouse.',
                severity='warning',
            )
            SystemAlert.objects.create(
                title='Transfer ACK-002 Delayed',
                description='Transfer from Kumasi to Accra is past expected delivery date.',
                severity='critical',
            )
            SystemAlert.objects.create(
                title='GH₵ Rate Updated',
                description='Bank forex rate updated. Review product costing.',
                severity='info',
            )
            self.stdout.write('  Created system alerts')
        else:
            self.stdout.write('  System alerts already exist')

        # --- Branch DB data ---
        set_current_branch_code(branch_code)

        from inventory.models import Category, Supplier, Product, StockAlert
        from dispatch.models import Customer, DispatchOrder, DispatchItem
        from receiving.models import InboundShipment, InboundItem
        from transfers.models import StockTransfer, TransferItem
        from returns.models import ReturnRequest, ReturnItem

        # Categories
        cats = {}
        for c in ('Electronics', 'Chemicals', 'Packaging'):
            cat, _ = Category.objects.get_or_create(name=c, defaults={'slug': c.lower()})
            cats[c] = cat
        self.stdout.write(f'  Created/verified {len(cats)} categories')

        # Suppliers
        supps = {}
        for s in [
            ('GlobalTech Supplies', 'info@globaltech.com', '+233-30-200-1000'),
            ('ChemCorp Ltd', 'orders@chemcorp.gh', '+233-30-200-2000'),
        ]:
            sup, _ = Supplier.objects.get_or_create(
                name=s[0],
                defaults={'contact_email': s[1], 'contact_phone': s[2], 'is_active': True},
            )
            supps[s[0]] = sup
        self.stdout.write(f'  Created/verified {len(supps)} suppliers')

        # Products
        products_data = [
            ('HDD-001', '500GB Hard Drive', 'Electronics', 120, 450.00, 15, 'BATCH-A1'),
            ('HDD-002', '1TB SSD Drive', 'Electronics', 85, 720.00, 10, 'BATCH-A2'),
            ('CHM-001', 'Industrial Solvent 5L', 'Chemicals', 200, 85.50, 25, 'CHM-2024-B'),
            ('CHM-002', 'Lab-grade Ethanol 1L', 'Chemicals', 45, 120.00, 20, 'CHM-2024-C'),
            ('PKG-001', 'Corrugated Box 40x30', 'Packaging', 500, 12.00, 100, 'PKG-B1'),
            ('PKG-002', 'Foam Wrap Roll 50m', 'Packaging', 300, 35.00, 50, 'PKG-B2'),
            ('HDD-003', '2TB External HDD', 'Electronics', 0, 550.00, 5, 'BATCH-A3'),
            ('CHM-003', 'Cleaning Solution 10L', 'Chemicals', 8, 200.00, 15, 'CHM-2024-D'),
            ('PKG-003', 'Sealing Tape 48mmx100m', 'Packaging', 1000, 8.50, 200, 'PKG-B3'),
            ('ELC-001', 'Power Supply Unit 500W', 'Electronics', 60, 250.00, 10, 'PSU-2024'),
        ]

        products = []
        for sku, name, cat_name, qty, cost, reorder, batch in products_data:
            p, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': cats.get(cat_name),
                    'stock_qty': qty,
                    'unit_cost': cost,
                    'reorder_level': reorder,
                    'batch_number': batch,
                },
            )
            if created:
                self.stdout.write(f'    Created product: {sku} ({name})')
            products.append(p)
        self.stdout.write(f'  Created/verified {len(products)} products')

        # Stock Alerts
        if not StockAlert.objects.exists():
            StockAlert.objects.create(product=Product.objects.get(sku='HDD-003'), alert_type='out_of_stock', message='2TB External HDD is out of stock', priority=True)
            StockAlert.objects.create(product=Product.objects.get(sku='CHM-003'), alert_type='low_stock', message='Cleaning Solution running low', priority=False)
            StockAlert.objects.create(product=Product.objects.get(sku='CHM-002'), alert_type='low_stock', message='Ethanol supply low', priority=False)
            self.stdout.write('  Created stock alerts')
        else:
            self.stdout.write('  Stock alerts already exist')

        # Customers
        custs = {}
        for c in [
            ('TechRetail Ghana Ltd', 'TR-001', 'Accra', 'Express', 'ok'),
            ('MedLab Supplies', 'ML-002', 'Kumasi', 'Standard', 'ok'),
        ]:
            cust, _ = Customer.objects.get_or_create(
                customer_id=c[1],
                defaults={'name': c[0], 'zone': c[2], 'shipping_method': c[3], 'credit_status': c[4]},
            )
            custs[c[1]] = cust
        self.stdout.write(f'  Created/verified {len(custs)} customers')

        # Dispatch Orders
        if not DispatchOrder.objects.exists():
            do1 = DispatchOrder.objects.create(customer=custs['TR-001'], destination='Accra Mall', carrier='swift', handling_fee=45, tax_rate=15)
            DispatchItem.objects.create(order=do1, product=products[0], quantity=10, unit_price=450.00)
            DispatchItem.objects.create(order=do1, product=products[1], quantity=5, unit_price=720.00)
            do1.subtotal = sum(i.line_total for i in do1.items.all())
            do1.status = 'processing'
            do1.save()

            do2 = DispatchOrder.objects.create(customer=custs['ML-002'], destination='Kumasi Medical Center', carrier='dhl', handling_fee=30, tax_rate=15)
            DispatchItem.objects.create(order=do2, product=products[2], quantity=20, unit_price=85.50)
            DispatchItem.objects.create(order=do2, product=products[4], quantity=50, unit_price=12.00)
            do2.subtotal = sum(i.line_total for i in do2.items.all())
            do2.status = 'pending'
            do2.save()

            do3 = DispatchOrder.objects.create(customer=custs['TR-001'], destination='Tema Warehouse', carrier='fedex', status='delivered')
            DispatchItem.objects.create(order=do3, product=products[0], quantity=5, unit_price=450.00)
            DispatchItem.objects.create(order=do3, product=products[4], quantity=20, unit_price=12.00)
            do3.subtotal = sum(i.line_total for i in do3.items.all())
            do3.save()
            self.stdout.write('  Created dispatch orders')
        else:
            self.stdout.write('  Dispatch orders already exist')

        # Inbound Shipments
        if not InboundShipment.objects.exists():
            import datetime
            s1 = InboundShipment.objects.create(supplier=supps['GlobalTech Supplies'], invoice_ref='INV-2024-001', po_reference='PO-1001', receive_date=datetime.date.today(), is_complete=True)
            InboundItem.objects.create(shipment=s1, product=products[0], quantity=50, unit_cost=420.00, condition='pristine')
            InboundItem.objects.create(shipment=s1, product=products[1], quantity=30, unit_cost=690.00, condition='pristine')

            s2 = InboundShipment.objects.create(supplier=supps['ChemCorp Ltd'], invoice_ref='INV-2024-002', po_reference='PO-1002', receive_date=datetime.date.today(), is_complete=False)
            InboundItem.objects.create(shipment=s2, product=products[2], quantity=100, unit_cost=80.00, condition='good')
            self.stdout.write('  Created inbound shipments')
        else:
            self.stdout.write('  Inbound shipments already exist')

        # Stock Transfers
        if not StockTransfer.objects.exists():
            t = StockTransfer.objects.create(from_branch_code='ACCRA', to_branch_code='ACCRA', status='draft', notes='Internal transfer')
            TransferItem.objects.create(transfer=t, product=products[3], quantity=10, weight_kg=5.0)
            self.stdout.write('  Created stock transfer')
        else:
            self.stdout.write('  Stock transfers already exist')

        # Return Requests
        if not ReturnRequest.objects.exists():
            do = DispatchOrder.objects.first()
            if do:
                rr = ReturnRequest.objects.create(original_order=do, reason='damaged_transit', return_type='partial', disposition='restock', return_date=datetime.date.today())
                ReturnItem.objects.create(return_request=rr, product=products[4], quantity=5, condition='damaged')
                self.stdout.write('  Created return request')
        else:
            self.stdout.write('  Return requests already exist')

        # ─── Fleet: Vehicles, Drivers, Assignments ───
        from fleet.models import Vehicle, Driver, DriverVehicleAssignment
        import datetime as _dt

        vehicles_data = [
            ('GR-1234-24', 'truck', 'Mercedes Sprinter 315CDI', 3500, 12.0, 'ACCRA'),
            ('GR-5678-24', 'pickup', 'Toyota Hilux 2.4L', 1200, 3.5, 'ACCRA'),
            ('GR-9012-25', 'van', 'Hyundai H-1 2.5CRDi', 900, 5.8, 'ACCRA'),
        ]
        vehs = {}
        for plate, vtype, make, weight, vol, branch in vehicles_data:
            v, _ = Vehicle.objects.get_or_create(
                plate_number=plate,
                defaults={
                    'vehicle_type': vtype, 'make_model': make,
                    'capacity_weight_kg': weight, 'capacity_volume_m3': vol,
                    'insurance_expiry': _dt.date(2027, 6, 30),
                    'last_service_date': _dt.date(2026, 3, 15),
                    'fitness_cert_expiry': _dt.date(2027, 6, 30),
                    'assigned_branch': branch,
                },
            )
            vehs[plate] = v
        self.stdout.write(f'  Created/verified {len(vehs)} vehicles')

        drivers_data = [
            ('Kwadwo', 'Mensah', 'DL-2024-001', '2028-05-20', '+233-24-555-1234', 'ACCRA'),
            ('Yaw', 'Boateng', 'DL-2024-002', '2027-12-31', '+233-20-666-5678', 'ACCRA'),
            ('Abena', 'Owusu', 'DL-2024-003', '2029-03-15', '+233-27-777-9012', 'ACCRA'),
        ]
        drvs = {}
        for first, last, lic, expiry, phone, branch in drivers_data:
            d, _ = Driver.objects.get_or_create(
                license_number=lic,
                defaults={
                    'first_name': first, 'last_name': last,
                    'license_expiry': _dt.date.fromisoformat(expiry),
                    'phone': phone, 'assigned_branch': branch,
                },
            )
            drvs[lic] = d
        self.stdout.write(f'  Created/verified {len(drvs)} drivers')

        assignments_data = [
            ('DL-2024-001', 'GR-1234-24'),
            ('DL-2024-002', 'GR-5678-24'),
            ('DL-2024-003', 'GR-9012-25'),
        ]
        for lic, plate in assignments_data:
            DriverVehicleAssignment.objects.get_or_create(
                driver=drvs[lic], vehicle=vehs[plate],
                defaults={'start_date': _dt.date(2026, 1, 1)},
            )
        self.stdout.write(f'  Created/verified {len(assignments_data)} driver-vehicle assignments')

        # Site Settings defaults
        settings = SiteSettings.get_settings()
        if settings.currency != 'GHS – Ghanaian Cedi':
            settings.currency = 'GHS – Ghanaian Cedi'
            settings.timezone = '(GMT+00:00) Africa/Accra'
            settings.date_format = 'DD/MM/YYYY'
            settings.save()
            self.stdout.write('  Updated site settings to Ghana defaults')

        self.stdout.write(self.style.SUCCESS('Seed data complete!'))
        self.stdout.write('')
        self.stdout.write('  Login credentials:')
        self.stdout.write('    Superuser: admin / admin123')
        self.stdout.write('    Staff:     warehouse1 / pass123')
