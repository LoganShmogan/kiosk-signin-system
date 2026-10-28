def member(**overrides):
    base = {
        "id": None,
        "first_name": "Jane",
        "last_name": "Smith",
        "date_of_birth": "2015-01-15",
        "school": "Test School",
        "mornings_days": "Mon,Tue",
        "afternoons_days": "Mon,Tue,Wed",
        "needs_pickup": 0,
        "activity": "Swimming",
        "activity_time": "4:30pm",
        "activity_address": "1 Pool Rd",
        "transport_required": 0,
        "activity_days": "Mon",
        "pin": "",
    }
    base.update(overrides)
    return base


def staff_member(**overrides):
    """Minimal data dict for a staff member (person_type='staff')."""
    base = {
        "id": None,
        "first_name": "Sam",
        "last_name": "Taylor",
        "date_of_birth": "",
        "school": "Team Leader",
        "mornings_days": "",
        "afternoons_days": "",
        "needs_pickup": 0,
        "activity": "",
        "activity_time": "",
        "activity_address": "",
        "transport_required": 0,
        "activity_days": "",
        "pin": "",
        "person_type": "staff",
    }
    base.update(overrides)
    return base


class FakeApp:
    """Stand-in for the kiosk App passed to every screen's __init__. Screens
    only ever call app.show_screen(name, **kwargs); this records each call
    so tests can assert on kiosk navigation without a real screen stack."""

    def __init__(self):
        self.calls = []

    def show_screen(self, name, **kwargs):
        self.calls.append((name, kwargs))

    @property
    def last_call(self):
        return self.calls[-1] if self.calls else None


def caregiver(member_id, **overrides):
    base = {
        "member_id": member_id,
        "full_name": "Bob Smith",
        "phone": "021-000-0000",
        "street_address": "1 Test St",
        "suburb": "Testville",
        "city": "Testton",
        "email": "bob@test.com",
        "emergency_contact_name": "Alice Smith",
        "emergency_contact_phone": "021-111-1111",
        "relationship": "Parent/Guardian",
        "notify_on": "BOTH",
    }
    base.update(overrides)
    return base
