from django.db import transaction
from core.db_router import register_branch_db
from core.branch_context import set_current_branch_code, get_branch_db_alias
from inventory.models import Product


def execute_transfer(transfer, waybill=None):
    if transfer.status not in ('in_transit', 'received', 'complete'):
        return

    from_alias = get_branch_db_alias(transfer.from_branch_code)
    to_alias = get_branch_db_alias(transfer.to_branch_code)

    register_branch_db(transfer.from_branch_code)
    register_branch_db(transfer.to_branch_code)

    for item in transfer.items.all():
        product_id = item.product_id
        qty = item.quantity

        set_current_branch_code(transfer.from_branch_code)
        src_product = Product.objects.using(from_alias).select_for_update().get(pk=product_id)

        # If a waybill exists, use received qty for destination, but still deduct full sent qty from source
        if waybill:
            try:
                wb_item = waybill.items.get(product__sku=src_product.sku)
                qty_received = wb_item.qty_received or 0
            except waybill.items.model.DoesNotExist:
                qty_received = qty
        else:
            qty_received = qty
        if src_product.stock_qty < qty:
            raise ValueError(f'Insufficient stock for {src_product.sku} (have {src_product.stock_qty}, need {qty})')
        src_product.stock_qty -= qty
        src_product.save(using=from_alias)

        set_current_branch_code(transfer.to_branch_code)
        dst_product, created = Product.objects.using(to_alias).get_or_create(
            sku=src_product.sku,
            defaults={
                'name': src_product.name,
                'category_id': None,
                'unit_cost': src_product.unit_cost,
                'reorder_level': src_product.reorder_level,
            }
        )
        dst_product.sourced_from_branch = transfer.from_branch_code
        dst_product.stock_qty += qty_received
        dst_product.save(using=to_alias)

    set_current_branch_code(transfer.from_branch_code)
