from playwright.sync_api import sync_playwright
import concurrent.futures
from datetime import datetime
import time
import io
from multiprocessing import Value

# Constants
MAX_WORKERS = 8
BATCH_SIZE = 30
NAVIGATION_TIMEOUT = 25000
SELECTOR_TIMEOUT = 15000
ROUTES_WITH_SEATS = Value('i', 0)
ROUTES_WITHOUT_SEATS = Value('i', 0)

def doubleEqualLine(file):
    file.write('='*84 + '\n')

def endExecution(file):
    file.write("\n\n")
    file.write('='*84 + '\n')
    file.write('|| ' + '~'*24 + ' ||   Finished Execution   || ' + '~'*24 + ' ||\n')
    file.write('='*84 + '\n')

def process_route(page, from_station, to_station, formatted_date):
    output_buffer = io.StringIO()
    has_available_seats = False
    url = f"https://eticket.railway.gov.bd/booking/train/search?fromcity={from_station}&tocity={to_station}&doj={formatted_date}&class=S_CHAIR"

    try:
        page.goto(url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        
        # Handle both success and error states
        no_trains = page.locator('span.no-ticket-found-first-msg')
        if no_trains.count() > 0:
            return output_buffer.getvalue(), False

        seat_elements = page.locator('.all-seats.text-left')
        has_available_seats = any(seat.inner_text() != '0' async for seat in seat_elements.all())

        # Update counters
        if has_available_seats:
            with ROUTES_WITH_SEATS.get_lock():
                ROUTES_WITH_SEATS.value += 1
            # Only process details if seats available
            output_buffer.write(f"\nFrom-To: {from_station}-{to_station}\n\n")
            
            trains = page.locator('app-single-trip')
            for idx in range(await trains.count()):
                train = trains.nth(idx)
                name = await train.locator('h2').inner_text()
                duration = await train.locator('.journey-duration').inner_text()
                start_time = (await train.locator('.journey-start .journey-date').inner_text()).split(', ')[1]
                end_time = (await train.locator('.journey-end .journey-date').inner_text()).split(', ')[1]
                
                output_buffer.write(f"({idx+1}) {name} ({start_time}-{end_time}) [{duration}]\n")
                
                seats = train.locator('.single-seat-class')
                for seat_idx in range(await seats.count()):
                    seat = seats.nth(seat_idx)
                    class_name = await seat.locator('.seat-class-name').inner_text()
                    fare = await seat.locator('.seat-class-fare').inner_text()
                    count = await seat.locator('.all-seats.text-left').inner_text()
                    output_buffer.write(f"    {class_name:<10}: {count:<4} ({fare})\n")
                
                output_buffer.write("\n")
        else:
            with ROUTES_WITHOUT_SEATS.get_lock():
                ROUTES_WITHOUT_SEATS.value += 1

    except Exception as e:
        output_buffer.write(f"Error processing {from_station}-{to_station}: {str(e)}\n")
    
    return output_buffer.getvalue(), has_available_seats

def process_batch(batch, formatted_date):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        results = []
        for from_station, to_station, route_index in batch:
            output, has_seats = process_route(page, from_station, to_station, formatted_date)
            results.append((from_station, to_station, route_index, output, has_seats))
        
        page.close()
        context.close()
        browser.close()
        return results

if __name__ == "__main__":
    # Auto-configured parameters
    current_date = datetime.now().strftime("%d-%m-%Y")
    formatted_date = datetime.strptime(current_date, "%d-%m-%Y").strftime("%d-%b-%Y")
    
    with open('stations.txt', 'r') as f:
        stations = [line.strip() for line in f]

    # Fixed range: index 1 (second station) to last station
    start_idx = 1
    end_idx = len(stations) - 1

    # Generate all combinations
    combinations = []
    route_index = 0
    for i in range(len(stations)):
        for j in range(max(i+1, start_idx), end_idx+1):
            combinations.append((stations[i], stations[j], route_index))
            route_index += 1

    total = len(combinations)
    batches = [combinations[i:i+BATCH_SIZE] for i in range(0, len(combinations), BATCH_SIZE)]
    
    start_time = time.time()
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_batch, batch, formatted_date) for batch in batches]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                batch_results = future.result()
                all_results.extend(batch_results)
            except Exception as e:
                print(f"Batch error: {e}")

    # Generate report
    all_results.sort(key=lambda x: x[2])
    no_train_routes = total - (ROUTES_WITH_SEATS.value + ROUTES_WITHOUT_SEATS.value)
    total_time = time.time() - start_time
    
    with open('output.txt', 'w', encoding='utf-8') as f:
        f.write(f"\n{' Ticket Availability Report ':=^84}\n\n")
        f.write(f"Report Date: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n")
        f.write(f"Journey Date: {formatted_date}\n")
        f.write(f"Total Routes Checked: {total}\n")
        f.write(f"Routes with seats: {ROUTES_WITH_SEATS.value}\n")
        f.write(f"Routes without seats: {ROUTES_WITHOUT_SEATS.value}\n")
        f.write(f"Routes with no service: {no_train_routes}\n")
        f.write(f"Execution Time: {total_time:.2f} seconds\n\n")
        
        for result in all_results:
            if result[4]:  # Only write successful routes
                doubleEqualLine(f)
                f.write(result[3])
        
        endExecution(f)

    print(f"\nReport generated in output.txt | Total time: {total_time/60:.1f} minutes")