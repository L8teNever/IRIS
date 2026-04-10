import os
import uuid
from datetime import datetime, timedelta
from flask import (
    render_template, request, redirect, url_for,
    jsonify, send_from_directory, abort, current_app
)
from werkzeug.utils import secure_filename
from models import db, Ticket, TicketLink, Attachment, Tag, Setting, CATEGORIES, PRIORITIES, STATUSES, MOODS

ALLOWED_MIME_PREFIXES = ('image/', 'application/pdf', 'text/')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'doc', 'docx', 'xlsx', 'csv', 'mp4', 'mp3', 'zip'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_setting(key, default=None):
    s = Setting.query.get(key)
    return s.value if s else default


def register_routes(app):

    # ─── Jinja2 filters ───────────────────────────────────────────────────────

    @app.template_filter('replace_sort')
    def replace_sort(args, col, current_sort, current_order):
        """Build query string with updated sort/order."""
        p = dict(args)
        p['sort'] = col
        p['order'] = 'desc' if (current_sort == col and current_order == 'asc') else 'asc'
        p.pop('page', None)
        return '&'.join(f'{k}={v}' for k, v in p.items())

    @app.template_filter('replace_page')
    def replace_page(args, page):
        """Build query string with updated page number."""
        p = dict(args)
        p['page'] = page
        return '&'.join(f'{k}={v}' for k, v in p.items())

    @app.context_processor
    def inject_globals():
        from datetime import datetime as _dt
        return {
            'categories': CATEGORIES,
            'priorities': PRIORITIES,
            'statuses': STATUSES,
            'moods': MOODS,
            'app_theme': _get_setting('theme', 'dark'),
            'app_name': _get_setting('app_name', 'IRIS'),
            'now': _dt.utcnow(),
        }

    # ─── Dashboard ────────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        total = Ticket.query.count()
        open_count = Ticket.query.filter_by(status='offen').count()

        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        this_week = Ticket.query.filter(
            Ticket.status == 'erledigt',
            Ticket.updated_at >= week_ago
        ).count()

        # Category counts
        category_data = {}
        for key, meta in CATEGORIES.items():
            category_data[key] = {
                'label': meta['label'],
                'count': Ticket.query.filter_by(category=key).count()
            }

        # Status counts
        status_data = {}
        for s in STATUSES:
            status_data[s['value']] = {
                'label': s['label'],
                'color': s['color'],
                'count': Ticket.query.filter_by(status=s['value']).count()
            }

        recent = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()

        most_active_cat = max(category_data.items(), key=lambda x: x[1]['count'], default=(None, {'label': '—', 'count': 0}))

        return render_template('dashboard.html',
            total=total,
            open_count=open_count,
            this_week=this_week,
            category_data=category_data,
            status_data=status_data,
            recent=recent,
            most_active_cat=most_active_cat,
        )

    # ─── Ticket List ──────────────────────────────────────────────────────────

    @app.route('/tickets')
    def ticket_list():
        q        = request.args.get('q', '').strip()
        category = request.args.get('category', '')
        status   = request.args.get('status', '')
        priority = request.args.get('priority', '')
        mood     = request.args.get('mood', '')
        tag      = request.args.get('tag', '')
        date_from = request.args.get('date_from', '')
        date_to   = request.args.get('date_to', '')
        sort      = request.args.get('sort', 'event_date')
        order     = request.args.get('order', 'desc')
        page      = int(request.args.get('page', 1))
        per_page  = int(request.args.get('per_page', 25))

        query = Ticket.query

        if q:
            like = f'%{q}%'
            query = query.filter(
                db.or_(
                    Ticket.title.ilike(like),
                    Ticket.description.ilike(like),
                    Ticket.tags.ilike(like),
                )
            )
        if category:
            query = query.filter_by(category=category)
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if mood:
            query = query.filter_by(mood=mood)
        if tag:
            query = query.filter(Ticket.tags.ilike(f'%{tag}%'))
        if date_from:
            try:
                query = query.filter(Ticket.event_date >= datetime.strptime(date_from, '%Y-%m-%d'))
            except ValueError:
                pass
        if date_to:
            try:
                query = query.filter(Ticket.event_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
            except ValueError:
                pass

        sort_col = getattr(Ticket, sort, Ticket.event_date)
        if order == 'asc':
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        active_filters = {}
        if q:        active_filters['q']        = q
        if category: active_filters['category'] = CATEGORIES.get(category, {}).get('label', category)
        if status:   active_filters['status']   = status
        if priority: active_filters['priority'] = priority
        if mood:     active_filters['mood']     = mood
        if tag:      active_filters['tag']      = tag
        if date_from: active_filters['date_from'] = date_from
        if date_to:   active_filters['date_to']   = date_to

        return render_template('tickets.html',
            tickets=pagination.items,
            pagination=pagination,
            active_filters=active_filters,
            sort=sort, order=order,
            args=request.args,
        )

    # ─── Create Ticket ────────────────────────────────────────────────────────

    @app.route('/tickets/new', methods=['GET', 'POST'])
    def create_ticket():
        if request.method == 'POST':
            ticket = _ticket_from_form(Ticket())
            db.session.add(ticket)
            db.session.flush()  # get ID before attachments
            _handle_attachments(ticket)
            _handle_links(ticket)
            db.session.commit()
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))

        default_cat = _get_setting('default_category', 'persoenlich')
        return render_template('create_ticket.html', ticket=None, default_cat=default_cat)

    # ─── Ticket Detail ────────────────────────────────────────────────────────

    @app.route('/tickets/<int:ticket_id>')
    def ticket_detail(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        linked = ticket.linked_tickets()
        return render_template('ticket_detail.html', ticket=ticket, linked=linked)

    # ─── Edit Ticket ──────────────────────────────────────────────────────────

    @app.route('/tickets/<int:ticket_id>/edit', methods=['GET', 'POST'])
    def ticket_edit(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        if request.method == 'POST':
            _ticket_from_form(ticket)
            ticket.updated_at = datetime.utcnow()
            _handle_attachments(ticket)
            _handle_links(ticket)
            db.session.commit()
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))
        linked_ids = [lnk['ticket'].id for lnk in ticket.linked_tickets()]
        return render_template('ticket_edit.html', ticket=ticket, linked_ids=linked_ids)

    # ─── Delete Ticket ────────────────────────────────────────────────────────

    @app.route('/tickets/<int:ticket_id>/delete', methods=['POST'])
    def ticket_delete(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        # Delete stored attachment files
        for att in ticket.attachments:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.stored_filename)
            if os.path.exists(path):
                os.remove(path)
        db.session.delete(ticket)
        db.session.commit()
        return redirect(url_for('ticket_list'))

    # ─── Quick Status Update (AJAX) ───────────────────────────────────────────

    @app.route('/tickets/<int:ticket_id>/status', methods=['POST'])
    def ticket_status_update(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        data = request.get_json()
        if data and 'status' in data:
            ticket.status = data['status']
            ticket.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'ok': True, 'status': ticket.status, 'status_label': ticket.status_label})
        return jsonify({'ok': False}), 400

    # ─── Timeline ─────────────────────────────────────────────────────────────

    @app.route('/timeline')
    def timeline():
        category  = request.args.get('category', '')
        date_from = request.args.get('date_from', '')
        date_to   = request.args.get('date_to', '')

        query = Ticket.query
        if category:
            query = query.filter_by(category=category)
        if date_from:
            try:
                query = query.filter(Ticket.event_date >= datetime.strptime(date_from, '%Y-%m-%d'))
            except ValueError:
                pass
        if date_to:
            try:
                query = query.filter(Ticket.event_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
            except ValueError:
                pass

        tickets = query.order_by(Ticket.event_date.desc()).all()

        # Group by date
        from collections import OrderedDict
        grouped = OrderedDict()
        for t in tickets:
            day = t.event_date.date()
            grouped.setdefault(day, []).append(t)

        return render_template('timeline.html', grouped=grouped, args=request.args)

    # ─── Settings ─────────────────────────────────────────────────────────────

    @app.route('/settings', methods=['GET', 'POST'])
    def settings_view():
        if request.method == 'POST':
            for key in ('theme', 'default_category'):
                val = request.form.get(key)
                if val is not None:
                    s = Setting.query.get(key)
                    if s:
                        s.value = val
                    else:
                        db.session.add(Setting(key=key, value=val))
            db.session.commit()
            return redirect(url_for('settings_view'))

        tags = Tag.query.order_by(Tag.name).all()
        theme = _get_setting('theme', 'dark')
        default_cat = _get_setting('default_category', 'persoenlich')
        return render_template('settings.html', tags=tags, theme=theme, default_cat=default_cat)

    @app.route('/settings/tags', methods=['POST'])
    def tag_create():
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'ok': False, 'error': 'Name fehlt'}), 400
        name = data['name'].strip()
        color = data.get('color', '#6750A4')
        if Tag.query.filter_by(name=name).first():
            return jsonify({'ok': False, 'error': 'Tag existiert bereits'}), 409
        tag = Tag(name=name, color=color)
        db.session.add(tag)
        db.session.commit()
        return jsonify({'ok': True, 'id': tag.id, 'name': tag.name, 'color': tag.color})

    @app.route('/settings/tags/<int:tag_id>', methods=['DELETE'])
    def tag_delete(tag_id):
        tag = Tag.query.get_or_404(tag_id)
        db.session.delete(tag)
        db.session.commit()
        return jsonify({'ok': True})

    # ─── API endpoints ────────────────────────────────────────────────────────

    @app.route('/api/subcategories')
    def api_subcategories():
        category = request.args.get('category', '')
        subs = CATEGORIES.get(category, {}).get('subs', [])
        return jsonify(subs)

    @app.route('/api/tags')
    def api_tags():
        tags = Tag.query.order_by(Tag.name).all()
        return jsonify([{'id': t.id, 'name': t.name, 'color': t.color} for t in tags])

    @app.route('/api/tickets/search')
    def api_ticket_search():
        q = request.args.get('q', '').strip()
        exclude = request.args.get('exclude', '')
        if not q:
            return jsonify([])
        like = f'%{q}%'
        query = Ticket.query.filter(
            db.or_(Ticket.title.ilike(like), Ticket.id == q if q.isdigit() else db.false())
        )
        if exclude.isdigit():
            query = query.filter(Ticket.id != int(exclude))
        tickets = query.limit(10).all()
        return jsonify([t.to_dict() for t in tickets])

    # ─── File uploads ─────────────────────────────────────────────────────────

    @app.route('/uploads/<filename>')
    def serve_upload(filename):
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

    # ─── Helper functions ─────────────────────────────────────────────────────

    def _ticket_from_form(ticket):
        ticket.title       = request.form.get('title', '').strip()
        ticket.category    = request.form.get('category', 'persoenlich')
        ticket.subcategory = request.form.get('subcategory', '') or None
        ticket.priority    = request.form.get('priority', 'mittel')
        ticket.status      = request.form.get('status', 'offen')
        ticket.mood        = request.form.get('mood', '') or None
        ticket.description = request.form.get('description', '') or None
        ticket.tags        = request.form.get('tags', '') or None

        date_str = request.form.get('event_date', '').strip()
        if date_str:
            try:
                ticket.event_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                ticket.event_date = datetime.utcnow()
        else:
            ticket.event_date = datetime.utcnow()

        return ticket

    def _handle_attachments(ticket):
        files = request.files.getlist('attachments')
        for f in files:
            if f and f.filename and _allowed_file(f.filename):
                original = secure_filename(f.filename)
                ext = original.rsplit('.', 1)[-1].lower()
                stored = f'{uuid.uuid4().hex}.{ext}'
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], stored))
                att = Attachment(
                    ticket_id=ticket.id,
                    filename=original,
                    stored_filename=stored,
                    mime_type=f.content_type,
                    file_size=None,
                )
                db.session.add(att)

    def _handle_links(ticket):
        # Remove existing links
        TicketLink.query.filter(
            db.or_(
                TicketLink.source_ticket_id == ticket.id,
                TicketLink.target_ticket_id == ticket.id,
            )
        ).delete()

        raw = request.form.get('linked_tickets', '')
        ids = [s.strip() for s in raw.split(',') if s.strip().isdigit()]
        seen = set()
        for tid in ids:
            tid_int = int(tid)
            if tid_int == ticket.id or tid_int in seen:
                continue
            if Ticket.query.get(tid_int):
                db.session.add(TicketLink(
                    source_ticket_id=ticket.id,
                    target_ticket_id=tid_int,
                    link_type='related',
                ))
                seen.add(tid_int)
