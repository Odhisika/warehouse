from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.views.decorators.http import require_POST
from django.utils import timezone
from fleet.models import Vehicle, Driver, DriverVehicleAssignment, TripSheet, ProofOfDelivery
from dispatch.models import DispatchOrder
from inventory.models import Product
from core.auth_helpers import branch_required, module_permission_required


# ─── VEHICLES ───

@login_required
@branch_required
@module_permission_required('shipping', 'view')
def vehicle_list(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'fleet/vehicle_list.html', {
        'page_title': 'Vehicles',
        'vehicles': vehicles,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    assignments = DriverVehicleAssignment.objects.filter(vehicle=vehicle).select_related('driver').order_by('-start_date')
    trips = TripSheet.objects.filter(vehicle=vehicle).select_related('driver', 'dispatch_order', 'transfer')[:20]
    current_driver_ids = assignments.filter(end_date__isnull=True).values_list('driver_id', flat=True)
    available_drivers = Driver.objects.filter(is_active=True).exclude(pk__in=current_driver_ids)
    all_drivers = Driver.objects.filter(is_active=True)
    return render(request, 'fleet/vehicle_detail.html', {
        'page_title': vehicle.plate_number,
        'vehicle': vehicle,
        'assignments': assignments,
        'trips': trips,
        'available_drivers': available_drivers,
        'all_drivers': all_drivers,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def vehicle_new(request):
    if request.method == 'POST':
        plate = request.POST.get('plate_number', '').strip().upper()
        if not plate:
            messages.error(request, 'Plate number is required.')
            return redirect('vehicle_new')
        if Vehicle.objects.filter(plate_number=plate).exists():
            messages.error(request, f'Vehicle with plate {plate} already exists.')
            return redirect('vehicle_new')
        vehicle = Vehicle.objects.create(
            plate_number=plate,
            vehicle_type=request.POST.get('vehicle_type', 'truck'),
            make_model=request.POST.get('make_model', ''),
            capacity_weight_kg=request.POST.get('capacity_weight_kg', 0),
            capacity_volume_m3=request.POST.get('capacity_volume_m3', 0),
            insurance_expiry=request.POST.get('insurance_expiry') or None,
            last_service_date=request.POST.get('last_service_date') or None,
            fitness_cert_expiry=request.POST.get('fitness_cert_expiry') or None,
            assigned_branch=request.POST.get('assigned_branch', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Vehicle {vehicle.plate_number} added.')
        return redirect('vehicle_detail', pk=vehicle.pk)
    return render(request, 'fleet/vehicle_form.html', {
        'page_title': 'Add Vehicle',
        'vehicle': None,
        'fleet_vehicle_types': Vehicle.VEHICLE_TYPE_CHOICES,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        vehicle.plate_number = request.POST.get('plate_number', vehicle.plate_number).strip().upper()
        vehicle.vehicle_type = request.POST.get('vehicle_type', vehicle.vehicle_type)
        vehicle.make_model = request.POST.get('make_model', '')
        vehicle.capacity_weight_kg = request.POST.get('capacity_weight_kg', 0)
        vehicle.capacity_volume_m3 = request.POST.get('capacity_volume_m3', 0)
        vehicle.insurance_expiry = request.POST.get('insurance_expiry') or None
        vehicle.last_service_date = request.POST.get('last_service_date') or None
        vehicle.fitness_cert_expiry = request.POST.get('fitness_cert_expiry') or None
        vehicle.assigned_branch = request.POST.get('assigned_branch', '')
        vehicle.status = request.POST.get('status', vehicle.status)
        vehicle.notes = request.POST.get('notes', '')
        vehicle.save()
        messages.success(request, f'Vehicle {vehicle.plate_number} updated.')
        return redirect('vehicle_detail', pk=vehicle.pk)
    return render(request, 'fleet/vehicle_form.html', {
        'page_title': f'Edit {vehicle.plate_number}',
        'vehicle': vehicle,
        'fleet_vehicle_types': Vehicle.VEHICLE_TYPE_CHOICES,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    plate = vehicle.plate_number
    vehicle.status = 'retired'
    vehicle.save()
    messages.success(request, f'Vehicle {plate} retired.')
    return redirect('vehicle_list')


# ─── DRIVERS ───

@login_required
@branch_required
@module_permission_required('shipping', 'view')
def driver_list(request):
    drivers = Driver.objects.all()
    return render(request, 'fleet/driver_list.html', {
        'page_title': 'Drivers',
        'drivers': drivers,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def driver_detail(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    assignments = DriverVehicleAssignment.objects.filter(driver=driver).select_related('vehicle').order_by('-start_date')
    trips = TripSheet.objects.filter(driver=driver).select_related('vehicle', 'dispatch_order', 'transfer')[:20]
    vehicles = Vehicle.objects.filter(status='active')
    return render(request, 'fleet/driver_detail.html', {
        'page_title': driver.full_name,
        'driver': driver,
        'assignments': assignments,
        'trips': trips,
        'vehicles': vehicles,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def driver_new(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        if not first_name or not license_number:
            messages.error(request, 'First name and license number are required.')
            return redirect('driver_new')
        driver = Driver.objects.create(
            first_name=first_name,
            last_name=request.POST.get('last_name', '').strip(),
            license_number=license_number,
            license_expiry=request.POST.get('license_expiry') or None,
            phone=request.POST.get('phone', ''),
            assigned_branch=request.POST.get('assigned_branch', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Driver {driver.full_name} added.')
        return redirect('driver_detail', pk=driver.pk)
    return render(request, 'fleet/driver_form.html', {
        'page_title': 'Add Driver',
        'driver': None,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def driver_edit(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == 'POST':
        driver.first_name = request.POST.get('first_name', driver.first_name).strip()
        driver.last_name = request.POST.get('last_name', '').strip()
        driver.license_number = request.POST.get('license_number', driver.license_number).strip()
        driver.license_expiry = request.POST.get('license_expiry') or None
        driver.phone = request.POST.get('phone', '')
        driver.assigned_branch = request.POST.get('assigned_branch', '')
        driver.is_active = request.POST.get('is_active') == 'on'
        driver.notes = request.POST.get('notes', '')
        driver.save()
        messages.success(request, f'Driver {driver.full_name} updated.')
        return redirect('driver_detail', pk=driver.pk)
    return render(request, 'fleet/driver_form.html', {
        'page_title': f'Edit {driver.full_name}',
        'driver': driver,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def driver_delete(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    name = driver.full_name
    driver.is_active = False
    driver.save()
    messages.success(request, f'Driver {name} deactivated.')
    return redirect('driver_list')


# ─── DRIVER-VEHICLE ASSIGNMENTS ───

@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def assign_driver_vehicle(request):
    driver_id = request.POST.get('driver_id')
    vehicle_id = request.POST.get('vehicle_id')
    start_date = request.POST.get('start_date')
    if not driver_id or not vehicle_id or not start_date:
        messages.error(request, 'Driver, vehicle, and start date are required.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    driver = get_object_or_404(Driver, pk=driver_id)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)

    existing = DriverVehicleAssignment.objects.filter(
        driver=driver, end_date__isnull=True
    ).first()
    if existing:
        existing.end_date = start_date
        existing.save()

    DriverVehicleAssignment.objects.create(
        driver=driver, vehicle=vehicle, start_date=start_date
    )
    messages.success(request, f'{driver.full_name} assigned to {vehicle.plate_number}.')
    return redirect('vehicle_detail', pk=vehicle.pk)


# ─── TRIP SHEETS ───

@login_required
@branch_required
@module_permission_required('shipping', 'view')
def trip_list(request):
    trips = TripSheet.objects.select_related('vehicle', 'driver', 'dispatch_order', 'transfer').all()
    return render(request, 'fleet/trip_list.html', {
        'page_title': 'Trip Sheets',
        'trips': trips,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def trip_detail(request, pk):
    trip = get_object_or_404(
        TripSheet.objects.select_related('vehicle', 'driver', 'dispatch_order', 'transfer'), pk=pk
    )
    return render(request, 'fleet/trip_detail.html', {
        'page_title': trip.trip_number,
        'trip': trip,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'create')
def trip_new(request):
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        driver_id = request.POST.get('driver')
        if not vehicle_id or not driver_id:
            messages.error(request, 'Vehicle and driver are required.')
            return redirect('trip_new')
        trip = TripSheet.objects.create(
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            dispatch_order_id=request.POST.get('dispatch_order') or None,
            transfer_id=request.POST.get('transfer') or None,
            route=request.POST.get('route', ''),
            estimated_arrival=request.POST.get('estimated_arrival') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'{trip.trip_number} created.')
        return redirect('trip_detail', pk=trip.pk)
    return render(request, 'fleet/trip_form.html', {
        'page_title': 'New Trip',
        'trip': None,
        'vehicles': Vehicle.objects.filter(status='active'),
        'drivers': Driver.objects.filter(is_active=True),
        'dispatch_orders': DispatchOrder.objects.filter(status__in=['processing', 'shipped']),
    })


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def trip_depart(request, pk):
    trip = get_object_or_404(TripSheet, pk=pk)
    if trip.status != 'planned':
        messages.error(request, 'Only planned trips can depart.')
        return redirect('trip_detail', pk=pk)
    trip.odometer_start = request.POST.get('odometer_start', 0)
    trip.departure_time = timezone.now()
    trip.status = 'in_transit'
    trip.save()
    messages.success(request, f'{trip.trip_number} departed.')
    return redirect('trip_detail', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def trip_arrive(request, pk):
    trip = get_object_or_404(TripSheet, pk=pk)
    if trip.status != 'in_transit':
        messages.error(request, 'Only in-transit trips can arrive.')
        return redirect('trip_detail', pk=pk)
    trip.odometer_end = request.POST.get('odometer_end', 0)
    trip.fuel_cost = request.POST.get('fuel_cost', 0)
    trip.toll_cost = request.POST.get('toll_cost', 0)
    trip.driver_allowance = request.POST.get('driver_allowance', 0)
    trip.actual_arrival = timezone.now()
    trip.status = 'completed'
    trip.save()
    messages.success(request, f'{trip.trip_number} completed. Total cost: ₵{trip.total_trip_cost:.2f}')
    return redirect('trip_detail', pk=pk)


@login_required
@branch_required
@module_permission_required('shipping', 'edit')
@require_POST
def trip_cancel(request, pk):
    trip = get_object_or_404(TripSheet, pk=pk)
    if trip.status == 'completed':
        messages.error(request, 'Cannot cancel a completed trip.')
        return redirect('trip_detail', pk=pk)
    trip.status = 'cancelled'
    trip.save()
    messages.success(request, f'{trip.trip_number} cancelled.')
    return redirect('trip_detail', pk=pk)


# ─── PROOF OF DELIVERY ───

@login_required
@branch_required
@module_permission_required('shipping', 'edit')
def pod_capture(request, pk):
    order = get_object_or_404(DispatchOrder, pk=pk)
    if hasattr(order, 'pod'):
        messages.info(request, f'POD already exists for {order.dispatch_id}.')
        return redirect('pod_detail', pk=pk)
    if order.status != 'shipped':
        messages.error(request, f'Only shipped dispatches can receive POD. Current status: {order.get_status_display()}.')
        return redirect('dispatch_detail', pk=pk)
    if request.method == 'POST':
        recipient_name = request.POST.get('recipient_name', '').strip()
        if not recipient_name:
            messages.error(request, 'Recipient name is required.')
            return redirect('pod_capture', pk=pk)
        pod = ProofOfDelivery(
            dispatch_order=order,
            recipient_name=recipient_name,
            recipient_phone=request.POST.get('recipient_phone', ''),
            damage_notes=request.POST.get('damage_notes', ''),
            delivery_notes=request.POST.get('delivery_notes', ''),
            delivered_by=request.user,
        )
        lat = request.POST.get('gps_latitude')
        lng = request.POST.get('gps_longitude')
        if lat:
            try:
                pod.gps_latitude = float(lat)
            except (ValueError, TypeError):
                pass
        if lng:
            try:
                pod.gps_longitude = float(lng)
            except (ValueError, TypeError):
                pass
        # Handle canvas-drawn signature (base64 data URL)
        sig_data = request.POST.get('signature_data', '')
        if sig_data and sig_data.startswith('data:image'):
            import base64
            from django.core.files.base import ContentFile
            fmt, imgstr = sig_data.split(',', 1)
            ext = 'png' if 'png' in fmt else 'jpeg'
            data = ContentFile(base64.b64decode(imgstr), name=f'sig_{pk}.{ext}')
            pod.signature_image = data
        elif request.FILES.get('signature_image'):
            pod.signature_image = request.FILES['signature_image']
        if request.FILES.get('delivery_photo'):
            pod.delivery_photo = request.FILES['delivery_photo']
        pod.save()
        order.status = 'delivered'
        order.save()
        messages.success(request, f'POD recorded for {order.dispatch_id}. Order marked as delivered.')
        return redirect('pod_detail', pk=pk)
    return render(request, 'fleet/pod_capture.html', {
        'page_title': f'POD — {order.dispatch_id}',
        'order': order,
    })


@login_required
@branch_required
@module_permission_required('shipping', 'view')
def pod_detail(request, pk):
    order = get_object_or_404(DispatchOrder, pk=pk)
    if not hasattr(order, 'pod'):
        messages.info(request, f'No POD exists for {order.dispatch_id}.')
        return redirect('dispatch_detail', pk=pk)
    return render(request, 'fleet/pod_detail.html', {
        'page_title': f'POD — {order.dispatch_id}',
        'order': order,
        'pod': order.pod,
    })
