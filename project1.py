import datetime
from db_base import DBbase
from populate_bookings import populate_bookings

#hotel capacity, sets bookings to 0, daily price per room
hotel = {
            "BASIC": {"total_rooms": 500, "available": 500, "rate": 79.99},
            "FAMILY": {"total_rooms": 400, "available": 400, "rate": 99.99},
            "SUITE": {"total_rooms": 200, "available": 200, "rate": 150},
            "PENTHOUSE": {"total_rooms": 40, "available": 40, "rate": 450},
        }

class Hotel(DBbase):
    
    def __init__(self, db_name):
        super().__init__(db_name)
        self.initialize_db()

    #creates database file with required tables/columns
    def initialize_db(self):
        self.execute_script("""
                                CREATE TABLE IF NOT EXISTS rooms (
                                    id INTEGER PRIMARY KEY,
                                    room_type TEXT,
                                    total_rooms INTEGER,
                                    available INTEGER,
                                    rate FLOAT
                                );

                                CREATE TABLE IF NOT EXISTS bookings (
                                    id INTEGER PRIMARY KEY,
                                    room_type TEXT,
                                    check_in DATE,
                                    check_out DATE
                                );
                                
                                CREATE TABLE IF NOT EXISTS reservations (
                                    reservation_id INTEGER PRIMARY KEY,
                                    booking_id INTEGER,
                                    last_name TEXT NOT NULL,
                                    first_name TEXT NOT NULL, 
                                    zip INTEGER NOT NULL,
                                    DOB DATE,
                                    FOREIGN KEY (booking_id) REFERENCES bookings(id)
                                );
                            """)

        #ensures rooms table has correct columns
        self.get_cursor.execute("SELECT COUNT(*) FROM rooms")
        if self.get_cursor.fetchone()[0] == 0:
            for room_type, column in hotel.items():
                self.get_cursor.execute("INSERT INTO rooms (room_type, total_rooms, available, rate) VALUES (?, ?, ?, ?)",
                                        (room_type, column['total_rooms'], column['available'], column['rate']))
            self.get_connection.commit()

    def search_reservation(self):
        reserved = int(input("Enter your Reservation ID: "))
        self.get_cursor.execute("""
                                SELECT res.first_name, res.last_name, r.room_type, b.check_in, b.check_out
                                FROM reservations res
                                JOIN bookings b ON res.booking_id = b.id
                                JOIN rooms r ON b.room_type = r.room_type 
                                WHERE res.reservation_id = ?;
                                """, (reserved,))
        
        results = self.get_cursor.fetchall()
        if results:
            for row in results:
                print(f"\nReservation Name: {row[0]} {row[1]}\nRoom Type: {row[2]}\nCheck-In Date:{row[3]}\nCheck-Out Date:{row[4]}\n")
        else:
            print("No reservations found for that ID.")


    def delete_reservation(self):
        reserved = int(input("Enter your Reservation ID: "))
        self.get_cursor.execute("""
            DELETE FROM reservations 
            WHERE reservation_id = ?;
        """, (reserved,))
        self.get_connection.commit()
        if self.get_cursor.rowcount > 0:
            print(f"Reservation ID {reserved} has been deleted.")
        else:
            print("That reservation was not found, please ensure accuracy")

    def update_reservation(self):
        reserved = int(input("Enter your Reservation ID: "))
        
        self.get_cursor.execute("SELECT * FROM reservations WHERE reservation_id = ?", (reserved,))
        if self.get_cursor.fetchone():
            print(f"Reservation ID {reserved} is available to update.")
            
            new_room_type = input("Enter the room you would like to book: ")
            new_check_in = input("Enter new check-in date (YYYY-MM-DD): ")
            new_check_out = input("Enter new check-out date (YYYY-MM-DD): ")
            
            self.get_cursor.execute("""
                                    UPDATE bookings
                                    SET check_in = ?, check_out = ?
                                    WHERE id = (SELECT booking_id FROM reservations WHERE reservation_id = ?);
                                    """, (new_check_in, new_check_out, reserved))
            
            if self.get_cursor.rowcount > 0:
                self.get_connection.commit()
                print(f"Reservation ID {reserved} has been successfully updated.")
            else:
                print("Failed to update reservation; please try again.")
        else:
            print("That reservation was not found, please ensure accuracy.")

    def welcome(self):
            print("="*50)
            print("Welcome to the Grand Py Hotel!!")
            print("="*50)
            print("Please select from the menu below by typing the number of the prompt")
            response = int(input(f"\n1. Book a Room\n2. Search for a previous reservation\n3. Update a previous reservation\n4. Delete a previous reservation\n: "))
            if response == 1:
                hotel_db.booking_room()
            elif response == 2:
                hotel_db.search_reservation()
            elif response == 3:
                hotel_db.update_reservation()
            elif response == 4:
                hotel_db.delete_reservation()
            else:
                print(f"Please enter one of the following options: 1 (Book), 2 (Search), 3 (Update), 4 (Delete)\n")
                return

    #pulls open rooms (used in booking and in initial availability display)
    def load_rooms(self):
        self.get_cursor.execute("SELECT room_type, available FROM rooms")
        return {row[0]: row[1] for row in self.get_cursor.fetchall()}

    #updates rooms based on database availability
    def update_room_availability(self, room_type, new_availability):
        self.get_cursor.execute("UPDATE rooms SET available = ? WHERE room_type = ?", (new_availability, room_type))
        self.get_connection.commit()

    #determines what rooms are booked on what nights. Used by several other functions to display availability to user
    def is_room_available(self, room_type, check_in, check_out):
        self.get_cursor.execute("""
            SELECT COUNT(*) 
            FROM bookings 
            WHERE room_type = ? 
            AND (
                (check_in <= ? AND check_out > ?) OR 
                (check_in < ? AND check_out >= ?)
            )
        """, (room_type, check_out, check_in, check_out, check_in))
        booked_count = self.get_cursor.fetchone()[0]

        #ensures that there are available rooms for each type
        self.get_cursor.execute("SELECT total_rooms FROM rooms WHERE room_type = ?", (room_type,))
        total_rooms = self.get_cursor.fetchone()[0]
        available_rooms = total_rooms - booked_count
        return available_rooms > 0, available_rooms
    
        #if room isn't available, this finds the next available night for the user (used in error handling at the end of the booking function)
    def find_next_available_date(self, room_type, check_in, nights):
        current_date = datetime.datetime.strptime(check_in, "%Y-%m-%d")
        while True:
            check_out = (current_date + datetime.timedelta(days=nights)).strftime("%Y-%m-%d")
            is_available, available_count = self.is_room_available(room_type, current_date.strftime("%Y-%m-%d"), check_out)
            if is_available:
                return current_date.strftime("%Y-%m-%d"), available_count
            current_date += datetime.timedelta(days=1)

    #functionality used in booking function
    def find_available_rooms_on_date(self, check_in, nights):
        available_rooms = {}
        for room_type in hotel.keys():
            is_available, available_count = self.is_room_available(room_type, check_in, check_in + datetime.timedelta(days=nights).strftime("%Y-%m-%d"))
            if is_available:
                available_rooms[room_type] = available_count
        return available_rooms

    #basic gui to make the program pretty for the user in terminal
    def available_rooms(self):
        print("-" * 50)
        print("Available Rooms Today: ")
        print("=" * 50)
        #ensures that the rooms displayed are accurate to today's date
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.get_cursor.execute("SELECT room_type, available, rate FROM rooms")
        rooms = self.get_cursor.fetchall()
        for room_type, available, rate in rooms:
            is_available, _ = self.is_room_available(room_type, today, today)
            if is_available:
                print(f"{room_type}: {available} available, Rate: ${rate:.2f}/night")
            else:
                print(f"{room_type} Rooms: 0 available, Rate: ${rate:.2f}/night")
            print("=" * 45)

    #functionality after booking is confirmed
    def print_receipt(self, name, reservation_id, room_type, check_in, check_out, total_cost):
        print("\nReceipt:")
        print(f"Name: {name}")
        print(f"Reservation ID: {reservation_id}")
        print(f"Room Type: {room_type}")
        print(f"Check-in Date: {check_in}")
        print(f"Check-out Date: {check_out}")
        print(f"Total Cost: ${total_cost:.2f}")

    def booking_room(self):
        hotel_db.available_rooms()
        while True:
            room_type = input("Which room do you want?: ").upper()
            nights = int(input("How many nights will you be staying?: "))
            check_in = input("Enter check-in date (YYYY-MM-DD): ")

            try:
                #converts check_in string to a datetime object usable for the program
                check_in_date = datetime.datetime.strptime(check_in, "%Y-%m-%d").date()

                #prevents fake dates / booking a room in the past
                if check_in_date < datetime.datetime.today().date():
                    print("You cannot book a date in the past. Please enter a valid date.")
                    continue

                #adds duration to check in date
                check_out_date = check_in_date + datetime.timedelta(days=nights)

                #pulls available rooms specific to the room type entered by the user
                if room_type in hotel:
                    available_rooms_db = self.load_rooms()
                    is_available, available_count = self.is_room_available(room_type, check_in, check_out_date.strftime("%Y-%m-%d"))

                    #basic math to calculate the cost of the room for the user's stay and remove a room from the database's availability
                    if is_available:
                        total_cost = hotel[room_type]['rate'] * nights
                        new_availability = available_rooms_db[room_type] - 1
                        self.update_room_availability(room_type, new_availability)

                        #books the user's room and adds row to bookings table, printing success message for user afterwards
                        self.get_cursor.execute("INSERT INTO bookings (room_type, check_in, check_out) VALUES (?, ?, ?)",
                                                (room_type, check_in, check_out_date.strftime("%Y-%m-%d")))
                        self.get_connection.commit()
                        booking_id = self.get_cursor.lastrowid
                        print(f"\nBooking successful! The {room_type} room has been booked from {check_in} to {check_out_date.strftime('%Y-%m-%d')}.")
                        print(f"Your total cost will be: ${total_cost:.2f}")

                        # Collect user information for the reservation
                        first_name = input("Enter your first name: ")
                        last_name = input("Enter your last name: ")
                        zip = int(input("Enter your billing ZIP code: "))
                        DOB = input("Enter your date of birth (YYYY-MM-DD): ")
                        DOB = datetime.datetime.strptime(DOB, "%Y-%m-%d").date()

                        #add reservation to the reservations table
                        self.get_cursor.execute("""
                            INSERT INTO reservations (booking_id, last_name, first_name, DOB, zip) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (booking_id, last_name, first_name, DOB, zip))
                        self.get_connection.commit()
                        print(f"Reservation created for {first_name} {last_name}.")
                        receipt_request = input("Would you like a receipt? (Y/N): ").lower()
                        if receipt_request == 'y':
                            name = first_name + " " + last_name
                            self.get_cursor.execute("SELECT reservation_id FROM reservations WHERE DOB = ?", (DOB,))
                            reservation_id = self.get_cursor.fetchone()[0]
                            self.print_receipt(name, reservation_id, room_type, check_in, check_out_date.strftime("%Y-%m-%d"), total_cost)
                        break

                    #if the original requested date isn't available, this finds the next open date for that specific room
                    else:
                        next_available_date, available_count = self.find_next_available_date(room_type, check_in, nights)
                        print(f"Sorry, the {room_type} room is not available for the selected dates.")
                        print(f"The next available date for a {nights}-night stay in the {room_type} room is: {next_available_date}.")
                        #option to rebook that room type at a later date
                        confirm_booking = input(f"Would you like to book the {room_type} room on {next_available_date}? (Y/N): ").lower()
                        if confirm_booking == 'y':
                            check_out_date = datetime.datetime.strptime(next_available_date, "%Y-%m-%d") + datetime.timedelta(days=nights)
                            total_cost = hotel[room_type]['rate'] * nights
                            new_availability = available_count - 1
                            self.update_room_availability(room_type, new_availability)

                            #updates the database with the booked room for the alternate date and offers receipt (copy/pasted from above code & modified)
                            self.get_cursor.execute("INSERT INTO bookings (room_type, check_in, check_out) VALUES (?, ?, ?)",
                                                    (room_type, next_available_date, check_out_date.strftime("%Y-%m-%d")))
                            self.get_connection.commit()
                            booking_id = self.get_cursor.lastrowid
                            first_name = input("Enter your first name: ")
                            last_name = input("Enter your last name: ")
                            zip = int(input("Enter your billing ZIP code: "))
                            DOB = input("Enter your date of birth (YYYY-MM-DD): ")
                            DOB = datetime.datetime.strptime(DOB, "%Y-%m-%d").date()

                            #insert reservation into reservations table
                            self.get_cursor.execute("""
                                INSERT INTO reservations (booking_id, last_name, first_name, DOB, zip) 
                                VALUES (?, ?, ?, ?, ?)
                            """, (booking_id, last_name, first_name, DOB, zip))
                            self.get_cursor.execute()

                            print(f"\nReservation created for {first_name} {last_name}.")
                            receipt_request = input("Would you like a receipt? (Y/N): ").lower()
                            if receipt_request == 'y':
                                self.print_receipt(room_type, next_available_date, check_out_date.strftime("%Y-%m-%d"), total_cost)
                            break

                #error handling for room type and date entered
                else:
                    print(f"Invalid room type '{room_type}'. Please choose a valid room type.")
            except ValueError:
                print("Invalid date format. Please enter the date in YYYY-MM-DD format.")
                        


#EXECUTION FLOW IS AS FOLLOWS:
    #create database file (doesn't need to be commented out after running the first time)
    #populates file with simulated bookings [leaving 10 rooms of each type open]
    #checks database for what rooms are available and print to console
    #functionality for booking room
    #closes database when finished running to prevent unwanted issues for user

hotel_db = Hotel('hotel_bookings.db')
populate_bookings('hotel_bookings.db')
hotel_db.welcome()
hotel_db.close_db()
