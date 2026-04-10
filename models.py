from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

CATEGORIES = {
    'arbeit': {
        'label': 'Arbeit / Beruf',
        'icon': 'work',
        'subs': []
    },
    'gesundheit': {
        'label': 'Gesundheit',
        'icon': 'favorite',
        'subs': []
    },
    'finanzen': {
        'label': 'Finanzen',
        'icon': 'payments',
        'subs': []
    },
    'persoenlich': {
        'label': 'Persönlich',
        'icon': 'person',
        'subs': []
    },
    'schule': {
        'label': 'Schule',
        'icon': 'school',
        'subs': [
            {'value': 'hausaufgaben', 'label': 'Hausaufgaben'},
            {'value': 'pruefungen',   'label': 'Prüfungen'},
            {'value': 'projekte',     'label': 'Projekte'},
        ]
    },
}

PRIORITIES = [
    {'value': 'kritisch', 'label': 'Kritisch', 'color': '#B3261E'},
    {'value': 'hoch',     'label': 'Hoch',     'color': '#E46962'},
    {'value': 'mittel',   'label': 'Mittel',   'color': '#F9A825'},
    {'value': 'niedrig',  'label': 'Niedrig',  'color': '#4CAF50'},
]

STATUSES = [
    {'value': 'offen',          'label': 'Offen',          'color': '#6750A4'},
    {'value': 'in_bearbeitung', 'label': 'In Bearbeitung', 'color': '#1565C0'},
    {'value': 'wartet',         'label': 'Wartet',         'color': '#795548'},
    {'value': 'erledigt',       'label': 'Erledigt',       'color': '#2E7D32'},
    {'value': 'abgebrochen',    'label': 'Abgebrochen',    'color': '#616161'},
]

MOODS = [
    {'value': 'gut',        'label': '😊 Gut',        'emoji': '😊'},
    {'value': 'neutral',    'label': '😐 Neutral',    'emoji': '😐'},
    {'value': 'schlecht',   'label': '😟 Schlecht',   'emoji': '😟'},
    {'value': 'frustriert', 'label': '😠 Frustriert', 'emoji': '😠'},
    {'value': 'gestresst',  'label': '😰 Gestresst',  'emoji': '😰'},
]


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(255), nullable=False)
    category    = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=True)
    priority    = db.Column(db.String(20), nullable=False, default='mittel')
    status      = db.Column(db.String(30), nullable=False, default='offen')
    mood        = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    tags        = db.Column(db.String(500), nullable=True)
    event_date  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    attachments    = db.relationship('Attachment', backref='ticket', cascade='all, delete-orphan', lazy=True)
    links_as_source = db.relationship('TicketLink', foreign_keys='TicketLink.source_ticket_id',
                                      backref='source', cascade='all, delete-orphan', lazy=True)
    links_as_target = db.relationship('TicketLink', foreign_keys='TicketLink.target_ticket_id',
                                      backref='target', cascade='all, delete-orphan', lazy=True)

    @property
    def tags_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def priority_color(self):
        colors = {'kritisch': '#B3261E', 'hoch': '#E46962', 'mittel': '#F9A825', 'niedrig': '#4CAF50'}
        return colors.get(self.priority, '#9E9E9E')

    @property
    def status_color(self):
        colors = {
            'offen': '#6750A4', 'in_bearbeitung': '#1565C0',
            'wartet': '#795548', 'erledigt': '#2E7D32', 'abgebrochen': '#616161'
        }
        return colors.get(self.status, '#9E9E9E')

    @property
    def mood_emoji(self):
        emojis = {'gut': '😊', 'neutral': '😐', 'schlecht': '😟', 'frustriert': '😠', 'gestresst': '😰'}
        return emojis.get(self.mood, '')

    @property
    def category_label(self):
        return CATEGORIES.get(self.category, {}).get('label', self.category)

    @property
    def category_icon(self):
        return CATEGORIES.get(self.category, {}).get('icon', 'label')

    @property
    def priority_label(self):
        labels = {'kritisch': 'Kritisch', 'hoch': 'Hoch', 'mittel': 'Mittel', 'niedrig': 'Niedrig'}
        return labels.get(self.priority, self.priority)

    @property
    def status_label(self):
        labels = {
            'offen': 'Offen', 'in_bearbeitung': 'In Bearbeitung',
            'wartet': 'Wartet', 'erledigt': 'Erledigt', 'abgebrochen': 'Abgebrochen'
        }
        return labels.get(self.status, self.status)

    def linked_tickets(self):
        linked = []
        for link in self.links_as_source:
            linked.append({'ticket': link.target, 'link_type': link.link_type})
        for link in self.links_as_target:
            linked.append({'ticket': link.source, 'link_type': link.link_type})
        return linked

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'category_label': self.category_label,
            'priority': self.priority,
            'status': self.status,
            'event_date': self.event_date.isoformat() if self.event_date else None,
        }


class TicketLink(db.Model):
    __tablename__ = 'ticket_links'

    id               = db.Column(db.Integer, primary_key=True)
    source_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False)
    target_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False)
    link_type        = db.Column(db.String(50), nullable=False, default='related')


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id              = db.Column(db.Integer, primary_key=True)
    ticket_id       = db.Column(db.Integer, db.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False)
    filename        = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    mime_type       = db.Column(db.String(100), nullable=True)
    file_size       = db.Column(db.Integer, nullable=True)
    uploaded_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Tag(db.Model):
    __tablename__ = 'tags'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    color      = db.Column(db.String(7), nullable=False, default='#6750A4')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Setting(db.Model):
    __tablename__ = 'settings'

    key   = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)
