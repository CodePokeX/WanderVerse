from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from .forms import TripForm
from .utils.geodb_api import get_city_coordinates
from .utils.geoapify_api import get_pois
from .utils.hotel_api import get_amadeus_token, get_city_code, get_hotels_in_city 
from .utils.gemini_api import generate_itinerary
from datetime import datetime, timedelta
import json
from django.contrib.auth.decorators import login_required
import firebase_admin
from firebase_admin import credentials, firestore
from accounts.firebase_auth import FirebaseAuth
import logging

logger = logging.getLogger(__name__)

# HOTELS_PER_PAGE constant is no longer needed for Amadeus hotel fetching

def create_trip(request):
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            city = form.cleaned_data['city']
            request.session['start_date'] = form.cleaned_data['start_date'].strftime('%Y-%m-%d')
            request.session['end_date'] = form.cleaned_data['end_date'].strftime('%Y-%m-%d')
            # Log activity
            if request.session.get('uid'):
                FirebaseAuth.log_user_activity(
                    request.session['uid'],
                    title='Created a new trip',
                    description=f"Created a new trip to {city} from {request.session['start_date']} to {request.session['end_date']}"
                )
            return redirect(reverse('show_trip_results', kwargs={'city_name': city}))
    else:
        form = TripForm()
    return render(request, 'trips/initiate_trip.html', {'form': form})


from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.safestring import mark_safe
import json

def show_trip_results(request, city_name):
    city_info = get_city_coordinates(city_name)
    context = {'city_name_searched': city_name}
    
    check_in_date_str = request.session.get('start_date') 
    check_out_date_str = request.session.get('end_date')

    if not city_info:
        messages.error(request, f"Sorry, city '{city_name}' could not be found.")
        return redirect(reverse('create_trip'))

    lat, lon = city_info['lat'], city_info['lon']
    
    # Fetch POIs with multiple categories
    pois = []
    categories = [
        'tourism.sights',
        'tourism.museum',
        'tourism.attraction',
        'tourism.historic',
        'tourism.art',
        'tourism.park',
        'tourism.viewpoint',
        'tourism.architecture',
        'tourism.monument',
        'tourism.cultural',
    ]
    
    for category in categories:
        category_pois = get_pois(lat, lon, category=[category])
        pois.extend(category_pois)
    
    # Remove duplicates based on name
    seen_names = set()
    unique_pois = []
    for poi in pois:
        name = poi.get('properties', {}).get('name')
        if name and name not in seen_names:
            seen_names.add(name)
            unique_pois.append(poi)
    
    pois = unique_pois[:20]  # Limit to 20 unique POIs

    token = get_amadeus_token()
    hotels_list = []

    if not token:
        messages.warning(request, "Failed to authenticate for hotel search. Hotel list may be unavailable.")
    else:
        city_code = get_city_code(city_name, token)
        if not city_code:
            messages.warning(request, f"Could not find IATA code for '{city_name}'. Hotel list may be unavailable.")
        else:
            print(f"Fetching hotel details for city code: {city_code}")
            hotel_data_response = get_hotels_in_city(city_code, token)
            hotels_list = hotel_data_response.get("hotels", [])

            if not hotels_list:
                messages.info(request, f"No hotels found for '{city_name}' via Amadeus.")
            else:
                print(f"--- Hotels Data from get_hotels_in_city in View ({city_name}) - Count: {len(hotels_list)} ---")

    # JSON serialization and marking as safe
    pois_json = mark_safe(json.dumps(pois))
    hotels_json = mark_safe(json.dumps(hotels_list))

    context.update({
        'city_name': city_name,
        'city_info': city_info,
        'pois': pois,  # Still used for template looping
        'hotels': hotels_list,  # Still used for template looping
        'pois_json': pois_json,
        'hotels_json': hotels_json,
        'check_in_date': check_in_date_str,
        'check_out_date': check_out_date_str
    })
    return render(request, 'trips/trip_results.html', context)


# load_more_hotels_ajax view is removed as it's no longer needed for Amadeus hotels

def ai_itinerary_form(request, city_name):
    """Display the AI itinerary generation form"""
    return render(request, 'trips/ai_itinerary.html', {
        'city_name': city_name
    })

def generate_ai_itinerary(request, city_name):
    """Handle the AI itinerary generation form submission"""
    if request.method == 'POST':
        try:
            # Get form data
            prompt = request.POST.get('prompt')
            travel_style = request.POST.get('travel_style', 'balanced')
            budget = request.POST.get('budget', 'medium')
            
            if not prompt:
                messages.error(request, 'Please provide a prompt for the itinerary generation.')
                return redirect('ai_itinerary_form', city_name=city_name)
            
            # Get dates from session
            check_in_date_str = request.session.get('start_date')
            check_out_date_str = request.session.get('end_date')
            
            # Debug logging
            print(f"Session dates in generate_ai_itinerary:")
            print(f"Start date: {check_in_date_str}")
            print(f"End date: {check_out_date_str}")
            print(f"Session keys: {request.session.keys()}")
            
            if not check_in_date_str or not check_out_date_str:
                messages.error(request, 'Missing date information. Please start over.')
                return redirect('create_trip')
            
            # Generate itinerary with custom prompt
            itinerary = generate_itinerary(
                city_name=city_name,
                start_date=check_in_date_str,
                end_date=check_out_date_str,
                preferences={
                    "prompt": prompt,
                    "travel_style": travel_style,
                    "budget": budget
                }
            )
            
            # Store the itinerary in session for display
            request.session['ai_itinerary'] = itinerary
            
            # Make sure dates are still in session
            request.session['start_date'] = check_in_date_str
            request.session['end_date'] = check_out_date_str
            
            # Redirect to display the generated itinerary
            return redirect('show_ai_itinerary', city_name=city_name)
            
        except Exception as e:
            messages.error(request, f'Error generating itinerary: {str(e)}')
            return redirect('ai_itinerary_form', city_name=city_name)
    
    return redirect('ai_itinerary_form', city_name=city_name)

def show_ai_itinerary(request, city_name):
    """Display the generated AI itinerary"""
    itinerary = request.session.get('ai_itinerary')
    start_date = request.session.get('start_date')
    
    # Debug logging
    print(f"Session start_date: {start_date}")
    print(f"Session keys: {request.session.keys()}")
    print(f"Itinerary data: {itinerary}")
    
    if not itinerary:
        messages.error(request, 'No itinerary found. Please generate one first.')
        return redirect('ai_itinerary_form', city_name=city_name)
    
    if not start_date:
        messages.warning(request, 'Start date not found in session. Please start over.')
        return redirect('create_trip')
    
    # Calculate dates for each day
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        print(f"Parsed start date: {start}")
        
        # Make sure itinerary has the expected structure
        if 'itinerary' not in itinerary:
            print("Warning: 'itinerary' key not found in data")
            itinerary = {'itinerary': itinerary}
        
        for day in itinerary['itinerary']:
            day_number = day.get('day', 1) - 1  # Convert to 0-based index
            current_date = start + timedelta(days=day_number)
            day['date'] = current_date.strftime('%Y-%m-%d')
            print(f"Calculated date for day {day_number + 1}: {day['date']}")
            
    except ValueError as e:
        print(f"Error calculating dates: {e}")
        messages.error(request, 'Error calculating dates. Please try again.')
        return redirect('create_trip')
    except Exception as e:
        print(f"Unexpected error: {e}")
        messages.error(request, 'An error occurred. Please try again.')
        return redirect('create_trip')
    
    return render(request, 'trips/show_ai_itinerary.html', {
        'city_name': city_name,
        'itinerary': itinerary,
        'start_date': start_date
    })

def create_itinerary(request, city_name):
    """View for creating a manual itinerary"""
    # Get city info
    city_info = get_city_coordinates(city_name)
    if not city_info:
        messages.error(request, f"Sorry, city '{city_name}' could not be found.")
        return redirect(reverse('create_trip'))
    
    # Get dates from session
    check_in_date_str = request.session.get('start_date')
    check_out_date_str = request.session.get('end_date')
    
    if not check_in_date_str or not check_out_date_str:
        messages.error(request, 'Missing date information. Please start over.')
        return redirect('create_trip')
    
    # Get POIs and hotels for the city
    lat, lon = city_info['lat'], city_info['lon']
    
    # Fetch POIs
    pois = []
    categories = [
        'tourism.sights',
        'tourism.museum',
        'tourism.attraction',
        'tourism.historic',
        'tourism.art',
        'tourism.park',
        'tourism.viewpoint',
        'tourism.architecture',
        'tourism.monument',
        'tourism.cultural',
    ]
    
    for category in categories:
        category_pois = get_pois(lat, lon, category=[category])
        pois.extend(category_pois)
    
    # Remove duplicates
    seen_names = set()
    unique_pois = []
    for poi in pois:
        name = poi.get('properties', {}).get('name')
        if name and name not in seen_names:
            seen_names.add(name)
            unique_pois.append(poi)
    
    pois = unique_pois[:20]  # Limit to 20 unique POIs
    
    # Fetch hotels
    hotels_list = []
    token = get_amadeus_token()
    if token:
        city_code = get_city_code(city_name, token)
        if city_code:
            hotel_data_response = get_hotels_in_city(city_code, token)
            hotels_list = hotel_data_response.get("hotels", [])
    
    context = {
        'city_name': city_name,
        'city_info': city_info,
        'pois': pois,
        'hotels': hotels_list,
        'check_in_date': check_in_date_str,
        'check_out_date': check_out_date_str
    }
    
    return render(request, 'trips/create_itinerary.html', context)

def my_trips(request):
    """Render the user's trips page"""
    if not request.session.get('uid'):
        messages.warning(request, 'Please sign in to view your trips')
        return redirect('/')
        
    try:
        # Get user data from Firestore to verify user exists
        user_data = FirebaseAuth.get_user_data(request.session['uid'])
        if not user_data:
            messages.error(request, 'Failed to load user data')
            return redirect('/')
            
        return render(request, 'trips/my_trips.html')
    except Exception as e:
        logger.error(f"Error loading trips page: {str(e)}")
        messages.error(request, 'An error occurred while loading your trips')
        return redirect('/')

def modify_trip(request, trip_id):
    """Show trip results for a saved trip, pre-filling all fields from Firestore."""
    if not request.session.get('uid'):
        messages.warning(request, 'Please sign in to modify trips')
        return redirect('/')
    try:
        db = firestore.client()
        trip_ref = db.collection('trips').document(trip_id)
        trip_doc = trip_ref.get()
        if not trip_doc.exists:
            messages.error(request, 'Trip not found')
            return redirect('my_trips')
        trip_data = trip_doc.to_dict()
        if trip_data['userId'] != request.session['uid']:
            messages.error(request, 'You do not have permission to modify this trip')
            return redirect('my_trips')
        # Log activity
        FirebaseAuth.log_user_activity(
            request.session['uid'],
            title='Modified a trip',
            description=f"Modified trip to {trip_data.get('city', 'Unknown City')} (Trip ID: {trip_id})"
        )
        # Use the saved city and dates
        def to_iso(date_val):
            # Firestore Timestamp or Python datetime
            if hasattr(date_val, 'isoformat'):
                return date_val.isoformat()[:10]
            # String already
            if isinstance(date_val, str):
                try:
                    # Try to parse and reformat
                    return datetime.fromisoformat(date_val).date().isoformat()
                except Exception:
                    return date_val
            return str(date_val)

        city_name = trip_data['city']
        start_date = to_iso(trip_data['startDate'])
        end_date = to_iso(trip_data['endDate'])
        # Get city info
        city_info = get_city_coordinates(city_name)
        if not city_info:
            messages.error(request, f"Sorry, city '{city_name}' could not be found.")
            return redirect('my_trips')
        lat, lon = city_info['lat'], city_info['lon']
        # Fetch POIs
        pois = []
        categories = [
            'tourism.sights', 'tourism.museum', 'tourism.attraction', 'tourism.historic',
            'tourism.art', 'tourism.park', 'tourism.viewpoint', 'tourism.architecture',
            'tourism.monument', 'tourism.cultural',
        ]
        for category in categories:
            category_pois = get_pois(lat, lon, category=[category])
            pois.extend(category_pois)
        seen_names = set()
        unique_pois = []
        for poi in pois:
            name = poi.get('properties', {}).get('name')
            if name and name not in seen_names:
                seen_names.add(name)
                unique_pois.append(poi)
        pois = unique_pois[:20]
        # Fetch hotels
        token = get_amadeus_token()
        hotels_list = []
        if token:
            city_code = get_city_code(city_name, token)
            if city_code:
                hotel_data_response = get_hotels_in_city(city_code, token)
                hotels_list = hotel_data_response.get("hotels", [])
        # JSON serialization and marking as safe
        pois_json = mark_safe(json.dumps(pois))
        hotels_json = mark_safe(json.dumps(hotels_list))
        # Use the saved itinerary if present
        itinerary_json = mark_safe(json.dumps(trip_data.get('itinerary', {})))
        context = {
            'city_name': city_name,
            'city_info': city_info,
            'pois': pois,
            'hotels': hotels_list,
            'pois_json': pois_json,
            'hotels_json': hotels_json,
            'check_in_date': start_date,
            'check_out_date': end_date,
            'itinerary_json': itinerary_json,
            'trip_id': trip_id,
        }
        return render(request, 'trips/trip_results.html', context)
    except Exception as e:
        logger.error(f"Error modifying trip: {str(e)}")
        messages.error(request, 'An error occurred while loading the trip')
        return redirect('my_trips')

def view_itinerary(request, trip_id):
    """Display the itinerary details for a specific trip"""
    if not request.session.get('uid'):
        messages.warning(request, 'Please sign in to view itineraries')
        return redirect('/')
    try:
        db = firestore.client()
        trip_ref = db.collection('trips').document(trip_id)
        trip_doc = trip_ref.get()
        if not trip_doc.exists:
            messages.error(request, 'Trip not found')
            return redirect('my_trips')
        trip_data = trip_doc.to_dict()
        if trip_data['userId'] != request.session['uid']:
            messages.error(request, 'You do not have permission to view this itinerary')
            return redirect('my_trips')
        # Log activity
        FirebaseAuth.log_user_activity(
            request.session['uid'],
            title='Viewed an itinerary',
            description=f"Viewed itinerary for trip to {trip_data.get('city', 'Unknown City')} (Trip ID: {trip_id})"
        )
        itinerary_json = mark_safe(json.dumps(trip_data.get('itinerary', {})))
        context = {
            'itinerary_json': itinerary_json,
        }
        return render(request, 'trips/view_itinerary.html', context)
    except Exception as e:
        logger.error(f"Error viewing itinerary: {str(e)}")
        messages.error(request, 'An error occurred while loading the itinerary')
        return redirect('my_trips')