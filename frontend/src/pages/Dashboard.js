import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiPost, apiPatch, apiDelete, apiPostMultipart, API_BASE } from '../api';
import '../styles/Dashboard.css';
import '../styles/DashboardSidebar.css';
const CAMPUS_PREFIX = '/campus';

const ProfileIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const ChevronDown = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
);

const BellIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const FACILITY_MENU = [
  { id: 'campus', label: 'Campus' },
  { id: 'buildings', label: 'Buildings' },
  { id: 'floors', label: 'Floors' },
  { id: 'hostel-rooms', label: 'Hostel Rooms' },
  { id: 'dining', label: 'Mess/Dining' },
  { id: 'sports', label: 'Sports' },
  { id: 'academic-spaces', label: 'Academic Spaces' },
];

const FACILITY_TYPE_NAMES = { dining: 'dining', sports: 'sports', 'academic-spaces': 'academic_spaces' };
const ROOM_TYPES = ['Single', 'Double', 'Suite'];
const MEAL_SLOTS = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'lunch', label: 'Lunch' },
  { value: 'dinner', label: 'Dinner' },
  { value: 'snack', label: 'Snack' },
];

const MIN_HOSTEL_BOOKING_MS = 24 * 60 * 60 * 1000;
const MIN_OTHER_AREA_BOOKING_MS = 2 * 60 * 60 * 1000;

const USER_ROLE_OPTIONS = ['Admin', 'Facility Manager', 'Security', 'Student', 'Staff'];

const EMERGENCY_TARGET_ROLE_OPTIONS = ['Admin', 'Facility Manager', 'Security', 'Student', 'Staff'];

/** Dedupe registered + active bookers for hostel inmates modal. */
function mergeHostelInmateUsers(data) {
  if (!data) return [];
  const m = new Map();
  for (const u of [...(data.active_bookers || []), ...(data.registered_inmates || [])]) {
    if (u && u.id != null) m.set(Number(u.id), u);
  }
  return Array.from(m.values()).sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' }));
}

/** Rows for maintenance location detail popup from API `facility_detail`. */
function maintenanceLocationDetailRows(detail) {
  if (!detail || typeof detail !== 'object') return [];
  const kind = detail.kind;
  const rows = [];
  if (kind === 'hostel_room') {
    if (detail.roomno != null && detail.roomno !== '') rows.push(['Room number', String(detail.roomno)]);
    if (detail.room_type) rows.push(['Room type', String(detail.room_type)]);
    if (detail.building) rows.push(['Building', String(detail.building)]);
    if (detail.facility_type) rows.push(['Facility type', String(detail.facility_type)]);
    if (detail.id != null) rows.push(['Room ID', String(detail.id)]);
  } else if (kind === 'other_area') {
    if (detail.name) rows.push(['Area name', String(detail.name)]);
    if (detail.building) rows.push(['Building', String(detail.building)]);
    if (detail.facility_type) rows.push(['Facility type', String(detail.facility_type)]);
    if (detail.id != null) rows.push(['Area ID', String(detail.id)]);
  } else if (Object.keys(detail).length > 0) {
    Object.entries(detail).forEach(([k, v]) => {
      rows.push([k, v === null || v === undefined ? '—' : String(v)]);
    });
  }
  return rows;
}

const FACILITY_PREVIEW_IMAGES = {
  hostel_room: '/facilities/hostel.png',
  dining: '/facilities/dining.png',
  sports: '/facilities/sports.png',
  academic: '/facilities/academic.png',
};

const IOT_FACILITY_TYPE_FILTERS = [
  { value: 'all', label: 'All facility types' },
  { value: 'hostel', label: 'Hostel (all rooms)' },
  { value: 'mens_hostel', label: "Men's hostel" },
  { value: 'ladies_hostel', label: "Ladies' hostel" },
  { value: 'dining', label: 'Mess / dining' },
  { value: 'sports', label: 'Sports' },
  { value: 'academic_spaces', label: 'Academic spaces' },
];

function iotFacilityTypeLabel(row) {
  const d = row.facility_detail || {};
  if (d.facility_type_label) return d.facility_type_label;
  const k = row.facility_type_key;
  const opt = IOT_FACILITY_TYPE_FILTERS.find((o) => o.value === k);
  if (opt && k !== 'all') return opt.label;
  if (row.facility_scope === 'hostel_room') return 'Hostel room';
  if (row.facility_scope === 'other_area') return 'Other area';
  if (row.facility_scope) {
    const s = String(row.facility_scope);
    if (s.includes('_')) return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    return s;
  }
  return '—';
}

/** Name / Room No: never show raw facility_id — use room, area name, or API facility_name only. */
function iotNameOrRoomLabel(row) {
  const nor = row.name_or_room_no;
  if (nor != null && String(nor).trim() !== '') {
    const s = String(nor).trim();
    if (
      !/^Unknown (room|area) #/i.test(s) &&
      !/^#\d+$/.test(s) &&
      !/^ID\s*\d+$/i.test(s)
    ) {
      return s.split('·')[0].trim();
    }
  }
  const d = row.facility_detail || {};
  if (d.kind === 'hostel_room' && d.roomno != null && String(d.roomno).trim() !== '') {
    return String(d.roomno).trim();
  }
  if (d.kind === 'other_area' && d.name) return String(d.name).trim();
  if (d.kind === 'thingsboard') {
    if (d.roomno != null && String(d.roomno).trim() !== '') return String(d.roomno).trim();
    if (d.name != null && String(d.name).trim() !== '') return String(d.name).trim();
  }
  const fn = (row.facility_name && String(row.facility_name).trim()) || '';
  if (!fn || /^Unknown (room|area) #/i.test(fn)) {
    return '—';
  }
  if (/^#\d+$/.test(fn) || /^ID\s*\d+$/i.test(fn)) {
    return '—';
  }
  return fn.split('·')[0].trim();
}

function iotAlertValueDisplay(a) {
  if (a.display_value != null && String(a.display_value).trim() !== '') return a.display_value;
  if (a.reading_value != null && String(a.reading_value).trim() !== '') return a.reading_value;
  return '—';
}

const Dashboard = () => {
  const navigate = useNavigate();
  const profileRef = useRef(null);
  const facilitiesRef = useRef(null);
  const notifRef = useRef(null);

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [facilitiesOpen, setFacilitiesOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [facilityView, setFacilityView] = useState(null);
  const [campuses, setCampuses] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [floors, setFloors] = useState([]);
  const [otherAreas, setOtherAreas] = useState([]);
  const [hostelRooms, setHostelRooms] = useState([]);
  const [facilityTypes, setFacilityTypes] = useState([]);
  const [listLoading, setListLoading] = useState(false);

  const [buildingsFilterCampus, setBuildingsFilterCampus] = useState('');
  const [buildingsSearch, setBuildingsSearch] = useState('');
  const [floorsFilterBuilding, setFloorsFilterBuilding] = useState('');
  const [floorsSearch, setFloorsSearch] = useState('');
  const [otherFilterBuilding, setOtherFilterBuilding] = useState('');
  const [otherSearch, setOtherSearch] = useState('');
  const [otherTypeFilterBuilding, setOtherTypeFilterBuilding] = useState('');
  const [otherTypeSearch, setOtherTypeSearch] = useState('');
  const [hostelFilterBuilding, setHostelFilterBuilding] = useState('');
  const [hostelFilterFloor, setHostelFilterFloor] = useState('');
  const [hostelFilterFacilityType, setHostelFilterFacilityType] = useState('');
  const [hostelSearch, setHostelSearch] = useState('');
  const [bookings, setBookings] = useState([]);
  const [reviewBookingFilter, setReviewBookingFilter] = useState('pending');
  const [bookEditTarget, setBookEditTarget] = useState(null);
  const [editBookingStart, setEditBookingStart] = useState('');
  const [editBookingEnd, setEditBookingEnd] = useState('');

  const [modal, setModal] = useState(null);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const isAdmin = profile?.role === 'Admin';
  const canEdit = profile?.role === 'Admin' || profile?.role === 'Facility Manager';
  const isStaff = profile?.role === 'Staff';
  const canReviewBookings = canEdit || isStaff;
  const isSecurity = profile?.role === 'Security';
  const canViewIot = canEdit || isSecurity;
  const canEmergency = canEdit || isSecurity;
  const canBook = profile?.role === 'Student' || profile?.role === 'Staff';

  const [bookTarget, setBookTarget] = useState(null);
  const [bookingStart, setBookingStart] = useState('');
  const [bookingEnd, setBookingEnd] = useState('');
  const [bookingMealPreference, setBookingMealPreference] = useState('');
  const [bookingMealSlot, setBookingMealSlot] = useState('');
  const [bookingMenuIds, setBookingMenuIds] = useState([]);
  const [bookingMenuOptions, setBookingMenuOptions] = useState([]);
  const [bookingInvQty, setBookingInvQty] = useState({});
  const [bookingRequestVip, setBookingRequestVip] = useState(false);
  const [hostelPreview, setHostelPreview] = useState(null);
  const [userDetailModal, setUserDetailModal] = useState(null);

  const [stockModal, setStockModal] = useState(null);
  const [stockItems, setStockItems] = useState([]);
  const [stockNewName, setStockNewName] = useState('');
  const [stockNewQty, setStockNewQty] = useState(1);
  const [menuModal, setMenuModal] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [menuNew, setMenuNew] = useState({ meal_slot: 'breakfast', name: '', diet: 'either' });
  const [hostelOccupancyModal, setHostelOccupancyModal] = useState(null);
  const [hostelOccupancyData, setHostelOccupancyData] = useState(null);
  const [hostelOccupancyLoading, setHostelOccupancyLoading] = useState(false);
  const [hostelOccupancyError, setHostelOccupancyError] = useState('');

  const [notifications, setNotifications] = useState([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifLoading, setNotifLoading] = useState(false);

  const [iotSummary, setIotSummary] = useState(null);
  const [iotReadings, setIotReadings] = useState([]);
  const [iotAlerts, setIotAlerts] = useState([]);
  const [iotLoading, setIotLoading] = useState(false);
  const [iotError, setIotError] = useState('');
  const [iotSyncWarning, setIotSyncWarning] = useState('');
  const [iotFacilityTypeFilter, setIotFacilityTypeFilter] = useState('all');

  const [maintenanceTickets, setMaintenanceTickets] = useState([]);
  const [maintenanceLoading, setMaintenanceLoading] = useState(false);
  const [maintenanceError, setMaintenanceError] = useState('');
  const [mtStatusFilter, setMtStatusFilter] = useState('all');
  const [mtFormOpen, setMtFormOpen] = useState(false);
  const [mtTitle, setMtTitle] = useState('');
  const [mtDescription, setMtDescription] = useState('');
  const [mtResourceKind, setMtResourceKind] = useState('hostel_room');
  const [mtHostelRoomId, setMtHostelRoomId] = useState('');
  const [mtOtherAreaId, setMtOtherAreaId] = useState('');
  const [mtIssueViewModal, setMtIssueViewModal] = useState(null);
  const [mtLocationViewModal, setMtLocationViewModal] = useState(null);

  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState('');

  const [adminUsers, setAdminUsers] = useState([]);
  const [adminUsersLoading, setAdminUsersLoading] = useState(false);
  const [adminUsersError, setAdminUsersError] = useState('');
  const [userDrafts, setUserDrafts] = useState({});

  const [maintSchedules, setMaintSchedules] = useState([]);
  const [maintSchedLoading, setMaintSchedLoading] = useState(false);
  const [maintSchedError, setMaintSchedError] = useState('');
  const [schedFormOpen, setSchedFormOpen] = useState(false);
  const [schedTitle, setSchedTitle] = useState('');
  const [schedNotes, setSchedNotes] = useState('');
  const [schedResKind, setSchedResKind] = useState('hostel_room');
  const [schedHostelRoomId, setSchedHostelRoomId] = useState('');
  const [schedOtherAreaId, setSchedOtherAreaId] = useState('');
  const [schedStart, setSchedStart] = useState('');
  const [schedEnd, setSchedEnd] = useState('');

  const [emergencyDesc, setEmergencyDesc] = useState('');
  const [emergencyTargetRole, setEmergencyTargetRole] = useState('Student');
  const [emergencyError, setEmergencyError] = useState('');
  const [emergencyOk, setEmergencyOk] = useState('');
  const [profileEligibility, setProfileEligibility] = useState({ year: '', dept: '', tier: 'basic' });
  const [profileSaveMsg, setProfileSaveMsg] = useState('');

  const unreadNotifCount = notifications.filter((n) => !n.read).length;

  const visibleFacilityMenu = canBook
    ? FACILITY_MENU.filter((item) => !['campus', 'buildings', 'floors'].includes(item.id))
    : FACILITY_MENU;

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      navigate('/login');
      return;
    }
    fetch(`${API_BASE}/users/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setProfile)
      .catch(() => navigate('/login'))
      .finally(() => setLoading(false));
  }, [navigate]);

  useEffect(() => {
    if (!profile) return;
    setProfileEligibility({
      year: profile.year_of_study != null ? String(profile.year_of_study) : '',
      dept: profile.department || '',
      tier: profile.membership_tier || 'basic',
    });
    setProfileSaveMsg('');
  }, [profile]);

  const loadCampuses = async () => {
    setListLoading(true);
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/campuses`);
      setCampuses(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load campuses');
      setCampuses([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadBuildings = async () => {
    setListLoading(true);
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/buildings`);
      setBuildings(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load buildings');
      setBuildings([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadOtherAreas = async () => {
    setListLoading(true);
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/other-areas`);
      setOtherAreas(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load other areas');
      setOtherAreas([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadFloors = async () => {
    setListLoading(true);
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/floors`);
      setFloors(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load floors');
      setFloors([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadHostelRooms = async () => {
    setListLoading(true);
    try {
      const params = new URLSearchParams();
      if (hostelFilterBuilding) params.set('building_id', hostelFilterBuilding);
      if (hostelFilterFloor) params.set('floor_id', hostelFilterFloor);
      if (hostelFilterFacilityType) params.set('facility_type_id', hostelFilterFacilityType);
      const qs = params.toString();
      const url = `${CAMPUS_PREFIX}/hostel-rooms${qs ? `?${qs}` : ''}`;
      const data = await apiGet(url);
      setHostelRooms(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load hostel rooms');
      setHostelRooms([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadBookingsSilent = async () => {
    try {
      const data = await apiGet('/bookings');
      setBookings(Array.isArray(data) ? data : []);
    } catch (_) {
      setBookings([]);
    }
  };

  const loadNotifications = async () => {
    setNotifLoading(true);
    try {
      const data = await apiGet('/notifications?limit=80');
      setNotifications(Array.isArray(data) ? data : []);
    } catch (_) {
      setNotifications([]);
    } finally {
      setNotifLoading(false);
    }
  };

  const loadIotData = async () => {
    setIotLoading(true);
    setIotError('');
    setIotSyncWarning('');
    const isSec = profile?.role === 'Security';
    try {
      if (!isSec) {
        try {
          await apiPost('/iot/thingsboard/sync', {});
        } catch (syncErr) {
          const raw = syncErr.message || String(syncErr);
          const short = raw.length > 320 ? `${raw.slice(0, 320)}…` : raw;
          setIotSyncWarning(
            `ThingsBoard sync did not complete (${short}). Showing data already in SmartCampus.`,
          );
        }
      }
      const ft =
        !isSec && iotFacilityTypeFilter && iotFacilityTypeFilter !== 'all'
          ? `&facility_type_filter=${encodeURIComponent(iotFacilityTypeFilter)}`
          : '';
      const [summary, readings, alerts] = await Promise.all([
        apiGet('/iot/summary'),
        apiGet(`/iot/readings?limit=100${ft}`),
        apiGet(`/iot/alerts?status_filter=all&limit=80${ft}`),
      ]);
      setIotSummary(summary);
      setIotReadings(Array.isArray(readings) ? readings : []);
      setIotAlerts(Array.isArray(alerts) ? alerts : []);
    } catch (e) {
      setIotError(e.message || 'Failed to load IoT data');
      setIotSummary(null);
      setIotReadings([]);
      setIotAlerts([]);
    } finally {
      setIotLoading(false);
    }
  };

  const loadMaintenanceTickets = async () => {
    setMaintenanceLoading(true);
    setMaintenanceError('');
    try {
      const qs =
        mtStatusFilter && mtStatusFilter !== 'all'
          ? `?status_filter=${encodeURIComponent(mtStatusFilter)}`
          : '';
      const data = await apiGet(`/maintenance/tickets${qs}`);
      setMaintenanceTickets(Array.isArray(data) ? data : []);
    } catch (e) {
      setMaintenanceError(e.message || 'Failed to load maintenance issues');
      setMaintenanceTickets([]);
    } finally {
      setMaintenanceLoading(false);
    }
  };

  const submitMaintenanceTicket = async () => {
    if (!mtTitle.trim()) {
      setMaintenanceError('Please enter a short issue summary');
      return;
    }
    if (mtResourceKind === 'hostel_room' && !mtHostelRoomId) {
      setMaintenanceError('Select a hostel room');
      return;
    }
    if (mtResourceKind === 'other_area' && !mtOtherAreaId) {
      setMaintenanceError('Select a facility / area');
      return;
    }
    setSaving(true);
    setMaintenanceError('');
    try {
      const fd = new FormData();
      fd.append('title', mtTitle.trim());
      fd.append('description', (mtDescription || '').trim());
      if (mtResourceKind === 'hostel_room') {
        fd.append('hostel_room_id', String(mtHostelRoomId));
        fd.append('other_area_id', '');
      } else {
        fd.append('hostel_room_id', '');
        fd.append('other_area_id', String(mtOtherAreaId));
      }
      const input = document.getElementById('mt-file-input');
      if (input && input.files && input.files.length) {
        for (let i = 0; i < input.files.length; i += 1) {
          fd.append('files', input.files[i]);
        }
      }
      await apiPostMultipart('/maintenance/tickets', fd);
      setMtFormOpen(false);
      setMtTitle('');
      setMtDescription('');
      setMtHostelRoomId('');
      setMtOtherAreaId('');
      if (input) input.value = '';
      await loadMaintenanceTickets();
    } catch (e) {
      setMaintenanceError(e.message || 'Could not submit maintenance issue');
    } finally {
      setSaving(false);
    }
  };

  const updateMaintenanceStatus = async (ticketId, status) => {
    try {
      await apiPatch(`/maintenance/tickets/${ticketId}/status`, { status });
      await loadMaintenanceTickets();
    } catch (e) {
      setMaintenanceError(e.message || 'Update failed');
    }
  };

  const loadAnalytics = async () => {
    setAnalyticsLoading(true);
    setAnalyticsError('');
    try {
      const data = await apiGet('/analytics/dashboard');
      setAnalytics(data || null);
    } catch (e) {
      setAnalyticsError(e.message || 'Failed to load analytics');
      setAnalytics(null);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const loadAdminUsers = async () => {
    setAdminUsersLoading(true);
    setAdminUsersError('');
    try {
      const data = await apiGet('/users/admin/users');
      const rows = Array.isArray(data) ? data : [];
      setAdminUsers(rows);
      setUserDrafts(
        Object.fromEntries(
          rows.map((u) => [u.id, { role: u.role, is_active: u.is_active !== false }]),
        ),
      );
    } catch (e) {
      setAdminUsersError(e.message || 'Failed to load users');
      setAdminUsers([]);
      setUserDrafts({});
    } finally {
      setAdminUsersLoading(false);
    }
  };

  const patchAdminUser = async (userId, payload) => {
    setSaving(true);
    setAdminUsersError('');
    try {
      await apiPatch(`/users/admin/users/${userId}`, payload);
      await loadAdminUsers();
    } catch (e) {
      setAdminUsersError(e.message || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const loadMaintSchedules = async () => {
    setMaintSchedLoading(true);
    setMaintSchedError('');
    try {
      const data = await apiGet('/maintenance/schedules');
      setMaintSchedules(Array.isArray(data) ? data : []);
    } catch (e) {
      setMaintSchedError(e.message || 'Failed to load schedules');
      setMaintSchedules([]);
    } finally {
      setMaintSchedLoading(false);
    }
  };

  const [maintAllBookings, setMaintAllBookings] = useState([]);
  useEffect(() => {
    if (schedFormOpen && canEdit) {
      apiGet('/bookings?status_filter=all').then(d => setMaintAllBookings(Array.isArray(d) ? d : [])).catch(e => console.error(e));
    }
  }, [schedFormOpen, canEdit]);

  const maintConflictWarning = useMemo(() => {
    if (!schedFormOpen || schedResKind !== 'other_area' || !schedOtherAreaId || !schedStart || !schedEnd) return '';
    const st = new Date(schedStart);
    const en = new Date(schedEnd);
    if (Number.isNaN(st.getTime()) || Number.isNaN(en.getTime()) || en <= st) return '';
    const overlap = maintAllBookings.some(b => 
      b.other_area_id === Number(schedOtherAreaId) &&
      b.status !== 'rejected' &&
      new Date(b.start_time) < en &&
      new Date(b.end_time) > st
    );
    return overlap ? 'Maintenance schedule conflicts with an existing booking in this area.' : '';
  }, [schedFormOpen, schedResKind, schedOtherAreaId, schedStart, schedEnd, maintAllBookings]);

  const bookingMaintConflictWarning = useMemo(() => {
    if (!bookTarget || bookTarget.type === 'hostel_room' || !bookingStart || !bookingEnd) return '';
    const st = new Date(bookingStart);
    const en = new Date(bookingEnd);
    if (Number.isNaN(st.getTime()) || Number.isNaN(en.getTime()) || en <= st) return '';
    const overlap = maintSchedules.some(m => 
      m.other_area_id === bookTarget.id &&
      m.status !== 'cancelled' &&
      new Date(m.scheduled_start) < en &&
      new Date(m.scheduled_end) > st
    );
    return overlap ? 'Facility is under maintenance during these dates and cannot be booked.' : '';
  }, [bookTarget, bookingStart, bookingEnd, maintSchedules]);

  const submitMaintenanceSchedule = async () => {
    if (!schedTitle.trim()) {
      setMaintSchedError('Enter a title');
      return;
    }
    if (schedResKind === 'hostel_room' && !schedHostelRoomId) {
      setMaintSchedError('Select a hostel room');
      return;
    }
    if (schedResKind === 'other_area' && !schedOtherAreaId) {
      setMaintSchedError('Select a facility / area');
      return;
    }
    if (!schedStart || !schedEnd) {
      setMaintSchedError('Select start and end');
      return;
    }
    const st = new Date(schedStart);
    const en = new Date(schedEnd);
    if (en <= st) {
      setMaintSchedError('End must be after start');
      return;
    }
    setSaving(true);
    setMaintSchedError('');
    try {
      const body = {
        title: schedTitle.trim(),
        notes: (schedNotes || '').trim() || null,
        scheduled_start: st.toISOString(),
        scheduled_end: en.toISOString(),
        ...(schedResKind === 'hostel_room'
          ? { hostel_room_id: +schedHostelRoomId, other_area_id: null }
          : { hostel_room_id: null, other_area_id: +schedOtherAreaId }),
      };
      await apiPost('/maintenance/schedules', body);
      setSchedFormOpen(false);
      setSchedTitle('');
      setSchedNotes('');
      setSchedHostelRoomId('');
      setSchedOtherAreaId('');
      setSchedStart('');
      setSchedEnd('');
      await loadMaintSchedules();
    } catch (e) {
      setMaintSchedError(e.message || 'Could not create schedule');
    } finally {
      setSaving(false);
    }
  };

  const patchMaintScheduleStatus = async (id, status) => {
    try {
      await apiPatch(`/maintenance/schedules/${id}`, { status });
      await loadMaintSchedules();
    } catch (e) {
      setMaintSchedError(e.message || 'Update failed');
    }
  };

  const deleteMaintSchedule = async (id) => {
    if (!window.confirm('Delete this maintenance schedule?')) return;
    try {
      await apiDelete(`/maintenance/schedules/${id}`);
      await loadMaintSchedules();
    } catch (e) {
      setMaintSchedError(e.message || 'Delete failed');
    }
  };

  const submitEmergencyBroadcast = async () => {
    if (!emergencyDesc.trim()) {
      setEmergencyError('Enter a description');
      return;
    }
    setSaving(true);
    setEmergencyError('');
    setEmergencyOk('');
    try {
      const data = await apiPost('/emergency/broadcast', {
        description: emergencyDesc.trim(),
        target_role: emergencyTargetRole,
      });
      setEmergencyOk(`Sent to ${data.recipient_count} user(s) with role “${data.target_role}”.`);
      setEmergencyDesc('');
    } catch (e) {
      setEmergencyError(e.message || 'Failed to send');
    } finally {
      setSaving(false);
    }
  };

  const runAllocationEngine = async () => {
    setSaving(true);
    setError('');
    try {
      const data = await apiPost('/room-allocations/invite-unhoused', {});
      alert(`Hostel Allocation Engine completed successfully. Invites sent: ${data.invites_sent}`);
      if (facilityView === 'hostel-rooms') loadHostelRooms();
    } catch (e) {
      setError(e.message || 'Failed to run allocation engine');
    } finally {
      setSaving(false);
    }
  };

  const markNotificationRead = async (id) => {
    try {
      await apiPatch(`/notifications/${id}/read`, {});
      await loadNotifications();
    } catch (_) {
      /* ignore */
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      await apiPost('/notifications/read-all', {});
      await loadNotifications();
    } catch (_) {
      /* ignore */
    }
  };

  const acknowledgeAlert = async (alertId) => {
    try {
      await apiPatch(`/iot/alerts/${alertId}`, { status: 'acknowledged' });
      await loadIotData();
    } catch (e) {
      setIotError(e.message || 'Could not update alert');
    }
  };

  const loadBookings = async () => {
    setListLoading(true);
    try {
      let data;
      const onReviewPage = facilityView === 'review-bookings';
      if (onReviewPage && canReviewBookings) {
        const f = reviewBookingFilter || 'pending';
        data = await apiGet(`/bookings?status_filter=${encodeURIComponent(f)}`);
      } else {
        data = await apiGet('/bookings');
      }
      setBookings(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || 'Failed to load bookings');
      setBookings([]);
    } finally {
      setListLoading(false);
    }
  };

  const loadFacilityTypes = async () => {
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/facility-types`);
      setFacilityTypes(Array.isArray(data) ? data : []);
    } catch (_) {
      setFacilityTypes([]);
    }
  };

  useEffect(() => {
    if (!profile) return;
    if (facilityView === 'campus') {
      loadCampuses();
    } else if (facilityView === 'buildings') {
      loadBuildings();
      loadCampuses();
    } else if (facilityView === 'floors') {
      loadFloors();
      loadBuildings();
    } else if (facilityView === 'hostel-rooms') {
      loadFacilityTypes();
      loadBuildings();
      loadFloors();
    } else if (['dining', 'sports', 'academic-spaces'].includes(facilityView)) {
      loadOtherAreas();
      loadBuildings();
      loadFloors();
      loadFacilityTypes();
    }
  }, [profile, facilityView]);

  useEffect(() => {
    if (!profile) return;
    if (facilityView !== 'review-bookings' && facilityView !== 'bookings') return;
    loadBookings();
  }, [profile, facilityView, reviewBookingFilter]);

  useEffect(() => {
    if (profile && canBook) {
      loadBookingsSilent();
    }
  }, [profile, canBook]);

  useEffect(() => {
    if (!profile) return;
    loadNotifications();
    const t = setInterval(loadNotifications, 45000);
    return () => clearInterval(t);
  }, [profile]);

  useEffect(() => {
    if (!profile || !canBook) return;
    const params = new URLSearchParams(window.location.search);
    const autoRoomId = params.get('autoBookRoomId');
    if (autoRoomId) {
      (async () => {
        try {
          const room = await apiGet(`${CAMPUS_PREFIX}/hostel-rooms/${autoRoomId}`);
          if (room) {
            openBook('hostel_room', room.id, room.roomno, 'hostel_room');
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        } catch (e) {
          console.error('Failed to auto-open booking for room', autoRoomId, e);
        }
      })();
    }
  }, [profile, canBook]);

  useEffect(() => {
    if (!profile || facilityView !== 'iot-monitoring') return;
    loadIotData();
    const t = setInterval(loadIotData, 60000);
    return () => clearInterval(t);
  }, [profile, facilityView, iotFacilityTypeFilter]);

  useEffect(() => {
    if (!profile || facilityView !== 'maintenance') return;
    (async () => {
      try {
        const [hr, oa] = await Promise.all([
          apiGet(`${CAMPUS_PREFIX}/hostel-rooms`),
          apiGet(`${CAMPUS_PREFIX}/other-areas`),
        ]);
        setHostelRooms(Array.isArray(hr) ? hr : []);
        setOtherAreas(Array.isArray(oa) ? oa : []);
      } catch (_) {
        /* picklists optional */
      }
    })();
  }, [profile, facilityView]);

  useEffect(() => {
    if (!profile || facilityView !== 'maintenance') return;
    loadMaintenanceTickets();
  }, [profile, facilityView, mtStatusFilter]);

  useEffect(() => {
    if (!profile || facilityView !== 'analytics') return;
    loadAnalytics();
  }, [profile, facilityView]);

  useEffect(() => {
    if (!profile || facilityView !== 'user-admin') return;
    loadAdminUsers();
  }, [profile, facilityView]);

  useEffect(() => {
    if (!profile) return;
    loadMaintSchedules();
  }, [profile]);

  useEffect(() => {
    if (!profile || facilityView !== 'maintenance-schedule') return;
    (async () => {
      try {
        const [hr, oa] = await Promise.all([
          apiGet(`${CAMPUS_PREFIX}/hostel-rooms`),
          apiGet(`${CAMPUS_PREFIX}/other-areas`),
        ]);
        setHostelRooms(Array.isArray(hr) ? hr : []);
        setOtherAreas(Array.isArray(oa) ? oa : []);
      } catch (_) {
        /* picklists optional */
      }
    })();
  }, [profile, facilityView]);

  useEffect(() => {
    if (!bookTarget || bookTarget.facilityKey !== 'dining' || !bookingMealSlot) {
      setBookingMenuOptions([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const params = new URLSearchParams();
        params.set('meal_slot', bookingMealSlot);
        if (bookingMealPreference === 'veg' || bookingMealPreference === 'non_veg') {
          params.set('diet_filter', bookingMealPreference);
        }
        const data = await apiGet(
          `${CAMPUS_PREFIX}/dining-areas/${bookTarget.id}/menu-items?${params.toString()}`,
        );
        if (!cancelled) setBookingMenuOptions(Array.isArray(data) ? data : []);
      } catch (_) {
        if (!cancelled) setBookingMenuOptions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bookTarget, bookingMealSlot, bookingMealPreference]);

  useEffect(() => {
    if (!bookTarget || bookTarget.type !== 'hostel_room' || !bookingStart || !bookingEnd) {
      setHostelPreview(null);
      return;
    }
    const st = new Date(bookingStart);
    const en = new Date(bookingEnd);
    if (Number.isNaN(st.getTime()) || Number.isNaN(en.getTime()) || en <= st) {
      setHostelPreview(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const qs = new URLSearchParams({
          room_id: String(bookTarget.id),
          start_time: st.toISOString(),
          end_time: en.toISOString(),
        });
        const data = await apiGet(`/bookings/preview/hostel-room?${qs}`);
        if (!cancelled) setHostelPreview(data);
      } catch (_) {
        if (!cancelled) setHostelPreview(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bookTarget, bookingStart, bookingEnd]);

  useEffect(() => {
    if (profile && canBook && ['campus', 'buildings', 'floors'].includes(facilityView)) {
      setFacilityView(null);
    }
  }, [profile, canBook, facilityView]);

  useEffect(() => {
    if (facilityView === 'hostel-rooms' && profile) {
      loadHostelRooms();
    }
  }, [facilityView, profile, hostelFilterBuilding, hostelFilterFloor, hostelFilterFacilityType]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false);
      if (facilitiesRef.current && !facilitiesRef.current.contains(e.target)) setFacilitiesOpen(false);
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/');
  };

  const selectFacility = (id, opts) => {
    setFacilityView(id);
    if (!opts?.keepFacilitiesOpen) {
      setFacilitiesOpen(false);
    }
    setError('');
  };

  const normFacilityTypeName = (ft) => {
    const n = ft?.name;
    if (n && typeof n === 'object' && n.value != null) return String(n.value);
    return n != null ? String(n) : '';
  };

  /** IoT reading or alert row → facility page with the same filters as Recent readings. */
  const navigateIoTRowToFacility = async (row) => {
    setError('');
    setIotError('');
    const fk = row.facility_type_key;
    const scope = String(row.facility_scope || '').toLowerCase();
    const detail = row.facility_detail || {};
    const tbLabel = String(detail.facility_type_label || '').toLowerCase();
    const labelBucket = `${scope} ${tbLabel}`.trim().toLowerCase();

    let fts = facilityTypes;
    if (!Array.isArray(fts) || fts.length === 0) {
      try {
        fts = await apiGet(`${CAMPUS_PREFIX}/facility-types`);
        if (Array.isArray(fts)) setFacilityTypes(fts);
        else fts = [];
      } catch (_) {
        fts = [];
      }
    }

    const findFtId = (name) => {
      if (!name) return '';
      const want = String(name).toLowerCase();
      const ft = fts.find((x) => normFacilityTypeName(x).toLowerCase() === want);
      return ft ? String(ft.id) : '';
    };

    const otherViewByKey = {
      dining: 'dining',
      sports: 'sports',
      academic_spaces: 'academic-spaces',
    };

    const looksMensHostel =
      labelBucket.includes('hostel') &&
      (labelBucket.includes('mens') ||
        labelBucket.includes("men's") ||
        /\bmen\b/.test(labelBucket)) &&
      !labelBucket.includes('ladies') &&
      !labelBucket.includes('women');
    const looksLadiesHostel =
      labelBucket.includes('hostel') &&
      (labelBucket.includes('ladies') || labelBucket.includes('women'));

    const isHostel =
      scope === 'hostel_room' ||
      fk === 'mens_hostel' ||
      fk === 'ladies_hostel' ||
      detail.kind === 'hostel_room' ||
      detail.facility_type === 'mens_hostel' ||
      detail.facility_type === 'ladies_hostel' ||
      looksMensHostel ||
      looksLadiesHostel;

    if (isHostel) {
      let typeId = '';
      if (fk === 'mens_hostel' || fk === 'ladies_hostel') {
        typeId = findFtId(fk);
      } else if (
        detail.facility_type === 'mens_hostel' ||
        detail.facility_type === 'ladies_hostel'
      ) {
        typeId = findFtId(detail.facility_type);
      } else if (looksMensHostel) {
        typeId = findFtId('mens_hostel');
      } else if (looksLadiesHostel) {
        typeId = findFtId('ladies_hostel');
      }
      const rawDisplay = iotNameOrRoomLabel(row);
      const roomTerm =
        detail.roomno != null && String(detail.roomno).trim() !== ''
          ? String(detail.roomno).trim()
          : rawDisplay && rawDisplay !== '—'
            ? String(rawDisplay).trim()
            : String(row.facility_name || '')
              .split('·')[0]
              .trim()
              .replace(/^#\d+$/, '')
              .replace(/^ID\s*\d+$/i, '');
      setHostelFilterBuilding('');
      setHostelFilterFloor('');
      setHostelFilterFacilityType(typeId);
      setHostelSearch(roomTerm);
      setFacilitiesOpen(true);
      selectFacility('hostel-rooms', { keepFacilitiesOpen: true });
      return;
    }

    let otherKey = fk;
    if (!otherViewByKey[otherKey]) {
      if (detail.kind === 'other_area' && detail.facility_type) {
        otherKey = detail.facility_type;
      } else if (scope === 'other_area' && detail.facility_type) {
        otherKey = detail.facility_type;
      } else {
        otherKey = null;
      }
    }

    if (!otherKey && detail.kind === 'thingsboard') {
      const label = String(detail.facility_type_label || scope || '').toLowerCase();
      if (label.includes('dining') || label.includes('mess')) otherKey = 'dining';
      else if (label.includes('sport')) otherKey = 'sports';
      else if (label.includes('academic')) otherKey = 'academic_spaces';
    }

    const targetView = otherKey ? otherViewByKey[otherKey] : null;
    if (targetView) {
      const rawDisplay = iotNameOrRoomLabel(row);
      const nameTerm =
        detail.name != null && String(detail.name).trim() !== ''
          ? String(detail.name).trim()
          : rawDisplay && rawDisplay !== '—'
            ? String(rawDisplay).trim()
            : String(row.facility_name || '')
              .split('·')[0]
              .trim()
              .replace(/^#\d+$/, '')
              .replace(/^ID\s*\d+$/i, '');
      setOtherTypeFilterBuilding('');
      setOtherTypeSearch(nameTerm);
      setFacilitiesOpen(true);
      selectFacility(targetView, { keepFacilitiesOpen: true });
      return;
    }

    setIotError(
      'Could not open a facility list for this row (unknown facility type). Check Campus → facility setup.',
    );
  };

  /** Maintenance schedule row → same facility navigation as IoT (uses API facility_detail). */
  const navigateMaintScheduleToFacility = async (s) => {
    setMaintSchedError('');
    setError('');
    const d = s.facility_detail || {};
    if (d.kind === 'hostel_room') {
      const ft = d.facility_type || '';
      await navigateIoTRowToFacility({
        facility_type_key: ft,
        facility_scope: 'hostel_room',
        facility_detail: d,
        facility_name: d.roomno,
      });
      return;
    }
    if (d.kind === 'other_area') {
      const ft = d.facility_type || '';
      await navigateIoTRowToFacility({
        facility_type_key: ft,
        facility_scope: 'other_area',
        facility_detail: d,
        facility_name: d.name,
      });
    }
  };

  const filteredBuildings = buildings.filter((b) => {
    const matchCampus = !buildingsFilterCampus || b.campus_id === Number(buildingsFilterCampus);
    const matchSearch = !buildingsSearch.trim() || (b.name || '').toLowerCase().includes(buildingsSearch.trim().toLowerCase());
    return matchCampus && matchSearch;
  });

  const filteredOtherAreas = otherAreas.filter((a) => {
    const matchBuilding = !otherFilterBuilding || a.building_id === Number(otherFilterBuilding);
    const matchSearch = !otherSearch.trim() || (a.name || '').toLowerCase().includes(otherSearch.trim().toLowerCase());
    return matchBuilding && matchSearch;
  });

  const filteredFloors = floors.filter((f) => {
    const matchBuilding = !floorsFilterBuilding || f.building_id === Number(floorsFilterBuilding);
    const search = String(floorsSearch || '').trim();
    const matchSearch = !search || String(f.floor_no || '').includes(search);
    return matchBuilding && matchSearch;
  });

  const hostelFacilityTypes = facilityTypes.filter(
    (ft) => /hostel/i.test(ft.name || '') && (/men|ladies/i.test(ft.name || ''))
  );
  const hostelFacilityTypeOptions = hostelFacilityTypes.length > 0 ? hostelFacilityTypes : facilityTypes;

  const filteredHostelRooms = hostelRooms.filter((r) => {
    const matchSearch = !hostelSearch.trim() || (r.roomno || '').toLowerCase().includes(hostelSearch.trim().toLowerCase());
    return matchSearch;
  });

  const renderBookCell = (type, id, name, facilityKey) => {
    if (!canBook) return null;
    return (
      <td>
        <button type="button" className="facility-btn-book" onClick={() => openBook(type, id, name, facilityKey)}>
          Book
        </button>
      </td>
    );
  };

  const navigateBookingToFacility = async (b) => {
    setFormError('');
    if (b.hostel_room_id) {
       // Try local state first, fall back to API fetch
       let hr = hostelRooms.find((x) => x.id === b.hostel_room_id);
       if (!hr) {
         try {
           const all = await apiGet(`${CAMPUS_PREFIX}/hostel-rooms`);
           if (Array.isArray(all)) setHostelRooms(all);
           hr = (Array.isArray(all) ? all : []).find((x) => x.id === b.hostel_room_id);
         } catch (_) {}
       }
       if (!hr) return;
       setHostelFilterBuilding(hr.building_id ? String(hr.building_id) : '');
       setHostelFilterFloor(hr.floor_id ? String(hr.floor_id) : '');
       setHostelFilterFacilityType(hr.facility_type_id ? String(hr.facility_type_id) : '');
       setHostelSearch(hr.roomno || '');
       setFacilitiesOpen(true);
       selectFacility('hostel-rooms', { keepFacilitiesOpen: true });
    } else if (b.other_area_id) {
       // Try local state first, fall back to API fetch
       let oa = otherAreas.find((x) => x.id === b.other_area_id);
       let fts = facilityTypes;
       if (!oa) {
         try {
           const [allAreas, allFts] = await Promise.all([
             apiGet(`${CAMPUS_PREFIX}/other-areas`),
             facilityTypes.length ? Promise.resolve(facilityTypes) : apiGet(`${CAMPUS_PREFIX}/facility-types`),
           ]);
           if (Array.isArray(allAreas)) { setOtherAreas(allAreas); oa = allAreas.find((x) => x.id === b.other_area_id); }
           if (Array.isArray(allFts)) { setFacilityTypes(allFts); fts = allFts; }
         } catch (_) {}
       }
       if (!oa) return;
       const ft = fts.find((f) => f.id === oa.facility_type_id);

       let targetView = 'dining';
       if (ft) {
         const ftLower = String(ft.name).toLowerCase();
         if (ftLower.includes('sport')) targetView = 'sports';
         else if (ftLower.includes('academic')) targetView = 'academic-spaces';
       }

       setOtherTypeFilterBuilding(oa.building_id ? String(oa.building_id) : '');
       setOtherTypeSearch(oa.name || '');
       setFacilitiesOpen(true);
       selectFacility(targetView, { keepFacilitiesOpen: true });
    }
  };

  const formatInventories = (b) => {
    const inv = b.inventory_selections || [];
    if (inv.length) return `${inv.length} inventory item(s) selected`;
    return '—';
  };

  const getOtherAreasByType = (typeKey) => {
    const typeName = FACILITY_TYPE_NAMES[typeKey];
    const ftId = facilityTypes.find((ft) => ft.name === typeName)?.id;
    if (!ftId) return [];
    return otherAreas
      .filter((a) => a.facility_type_id === ftId)
      .filter((a) => {
        const matchBuilding = !otherTypeFilterBuilding || a.building_id === Number(otherTypeFilterBuilding);
        const matchSearch = !otherTypeSearch.trim() || (a.name || '').toLowerCase().includes(otherTypeSearch.trim().toLowerCase());
        return matchBuilding && matchSearch;
      });
  };

  const openAdd = (entity) => {
    if (entity === 'campus') setModal({ type: 'add', entity, data: { name: '', location: '' } });
    if (entity === 'buildings') setModal({ type: 'add', entity, data: { name: '', campus_id: campuses[0]?.id || 0 } });
    if (entity === 'floors') setModal({ type: 'add', entity, data: { building_id: buildings[0]?.id || 0, floor_no: 0 } });
    if (entity === 'hostel-rooms') {
      setModal({
        type: 'add',
        entity,
        data: {
          roomno: '',
          room_type: 'Single',
          facility_type_id: hostelFacilityTypeOptions[0]?.id || facilityTypes[0]?.id || 0,
          building_id: null,
          floor_id: null,
          inmate_profiles: [],
          room_capacity: 1,
          staff_only: false,
          eligReqYear: '',
          eligReqDept: '',
        },
      });
    }
    if (['dining', 'sports', 'academic-spaces'].includes(entity)) {
      const typeName = FACILITY_TYPE_NAMES[entity];
      const ftId = facilityTypes.find((ft) => ft.name === typeName)?.id || facilityTypes[0]?.id || 0;
      const bid = buildings[0]?.id || 0;
      const floorOpts = floors.filter((f) => f.building_id === bid);
      setModal({
        type: 'add',
        entity,
        data: {
          name: '',
          building_id: bid,
          floor_id: floorOpts[0]?.id || floors[0]?.id || 0,
          capacity: null,
          facility_type_id: ftId,
          active: true,
          staff_only: false,
          eligReqYear: '',
          eligReqDept: '',
        },
      });
    }
    setFormError('');
  };

  const openEdit = (entity, row) => {
    const data = { ...row };
    if (entity === 'hostel-rooms') {
      delete data.live_booking_count;
    }
    if (entity === 'hostel-rooms' || ['dining', 'sports', 'academic-spaces'].includes(entity)) {
      data.eligReqYear = data.eligibility_rules?.min_year || '';
      data.eligReqDept = data.eligibility_rules?.allowed_departments?.[0] || '';
    }
    setModal({ type: 'edit', entity, data, id: row.id });
    setFormError('');
  };

  const closeModal = () => {
    setModal(null);
  };

  const buildModalPayload = () => {
    if (!modal) return {};
    const raw = { ...modal.data };
    if (raw.eligReqYear !== undefined || raw.eligReqDept !== undefined) {
      if (raw.eligReqYear || raw.eligReqDept) {
        raw.eligibility_rules = {};
        if (raw.eligReqYear) raw.eligibility_rules.min_year = parseInt(raw.eligReqYear, 10);
        if (raw.eligReqDept) raw.eligibility_rules.allowed_departments = [raw.eligReqDept];
      } else {
        raw.eligibility_rules = null;
      }
      delete raw.eligibility_rules_text;
      delete raw.eligReqYear;
      delete raw.eligReqDept;
    }
    return raw;
  };

  const saveModal = async () => {
    if (!modal) return;
    setSaving(true);
    setFormError('');
    try {
      const pathMap = {
        campus: (id) => `${CAMPUS_PREFIX}/campuses${id != null ? `/${id}` : ''}`,
        buildings: (id) => `${CAMPUS_PREFIX}/buildings${id != null ? `/${id}` : ''}`,
        floors: (id) => `${CAMPUS_PREFIX}/floors${id != null ? `/${id}` : ''}`,
        'hostel-rooms': (id) => `${CAMPUS_PREFIX}/hostel-rooms${id != null ? `/${id}` : ''}`,
        dining: (id) => `${CAMPUS_PREFIX}/other-areas${id != null ? `/${id}` : ''}`,
        sports: (id) => `${CAMPUS_PREFIX}/other-areas${id != null ? `/${id}` : ''}`,
        'academic-spaces': (id) => `${CAMPUS_PREFIX}/other-areas${id != null ? `/${id}` : ''}`,
      };
      const path = pathMap[modal.entity](modal.id);
      if (modal.type === 'add') {
        let payload = buildModalPayload();
        if (modal.entity === 'hostel-rooms') {
          payload = { ...payload, inmate_profiles: payload.inmate_profiles || [] };
        }
        await apiPost(path, payload);
      } else {
        const built = buildModalPayload();
        const { id: _id, ...body } = built;
        await apiPatch(path, body);
      }
      closeModal();
      if (facilityView === 'campus') loadCampuses();
      if (facilityView === 'buildings') loadBuildings();
      if (facilityView === 'floors') loadFloors();
      if (facilityView === 'hostel-rooms') loadHostelRooms();
      if (['dining', 'sports', 'academic-spaces'].includes(facilityView)) loadOtherAreas();
    } catch (e) {
      setFormError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const openHostelOccupancyModal = async (roomId, roomno) => {
    setHostelOccupancyModal({ roomId, roomno });
    setHostelOccupancyData(null);
    setHostelOccupancyError('');
    setHostelOccupancyLoading(true);
    try {
      const data = await apiGet(`${CAMPUS_PREFIX}/hostel-rooms/${roomId}/live-occupancy`);
      setHostelOccupancyData(data);
    } catch (e) {
      setHostelOccupancyData(null);
      setHostelOccupancyError(e.message || 'Could not load profiles');
    } finally {
      setHostelOccupancyLoading(false);
    }
  };

  const closeHostelOccupancyModal = () => {
    setHostelOccupancyModal(null);
    setHostelOccupancyData(null);
    setHostelOccupancyError('');
  };

  const openBook = async (type, id, name, facilityKey) => {
    let inventoryItems = [];
    try {
      const q = type === 'hostel_room' ? `hostel_room_id=${id}` : `other_area_id=${id}`;
      const data = await apiGet(`${CAMPUS_PREFIX}/facility-inventory-items?${q}`);
      inventoryItems = Array.isArray(data) ? data : [];
    } catch (_) {
      inventoryItems = [];
    }
    setBookTarget({ type, id, name, facilityKey: facilityKey || 'hostel_room', inventoryItems });
    setBookingStart('');
    setBookingEnd('');
    setBookingMealPreference('');
    setBookingMealSlot('');
    setBookingMenuIds([]);
    setBookingMenuOptions([]);
    setBookingInvQty({});
    setBookingRequestVip(false);
    setHostelPreview(null);
    setFormError('');
  };

  const closeBookModal = () => {
    setBookTarget(null);
    setBookingStart('');
    setBookingEnd('');
    setBookingMealPreference('');
    setBookingMealSlot('');
    setBookingMenuIds([]);
    setBookingMenuOptions([]);
    setBookingInvQty({});
    setBookingRequestVip(false);
    setHostelPreview(null);
  };

  const submitBooking = async () => {
    if (!bookTarget) return;
    if (!bookingStart || !bookingEnd) {
      setFormError('Please select start and end time');
      return;
    }
    const start = new Date(bookingStart);
    const end = new Date(bookingEnd);
    if (end <= start) {
      setFormError('End time must be after start time');
      return;
    }
    const durMs = end - start;
    if (bookTarget.type === 'hostel_room') {
      if (durMs < MIN_HOSTEL_BOOKING_MS) {
        setFormError('Hostel bookings must be at least 1 day from start to end.');
        return;
      }
    } else if (durMs < MIN_OTHER_AREA_BOOKING_MS) {
      setFormError('Bookings for this facility must be at least 2 hours from start to end.');
      return;
    }
    if (bookTarget.facilityKey === 'dining') {
      if (!bookingMealSlot) {
        setFormError('Select a meal time (breakfast, lunch, …)');
        return;
      }
      if (!bookingMenuIds.length) {
        setFormError('Select at least one menu item');
        return;
      }
    }
    const invSelections = Object.entries(bookingInvQty)
      .map(([k, q]) => ({ inventory_item_id: +k, quantity: +q }))
      .filter((x) => x.quantity > 0 && x.inventory_item_id > 0);
    setSaving(true);
    setFormError('');
    try {
      let body;
      if (bookTarget.type === 'hostel_room') {
        body = {
          hostel_room_id: bookTarget.id,
          other_area_id: null,
          start_time: start.toISOString(),
          end_time: end.toISOString(),
          ...(invSelections.length ? { inventory_selections: invSelections } : {}),
        };
      } else {
        body = {
          hostel_room_id: null,
          other_area_id: bookTarget.id,
          start_time: start.toISOString(),
          end_time: end.toISOString(),
          ...(bookingRequestVip ? { request_vip: true } : {}),
          ...(bookTarget.facilityKey === 'dining'
            ? {
              meal_slot: bookingMealSlot,
              dining_menu_item_ids: bookingMenuIds,
              ...(bookingMealPreference ? { meal_preference: bookingMealPreference } : {}),
            }
            : {}),
          ...(invSelections.length ? { inventory_selections: invSelections } : {}),
        };
      }
      await apiPost('/bookings', body);
      closeBookModal();
      await loadBookingsSilent();
    } catch (e) {
      setFormError(e.message || 'Booking failed');
    } finally {
      setSaving(false);
    }
  };

  const openStockModal = async (scope, facilityId, title) => {
    setStockModal({ scope, facilityId, title });
    setStockNewName('');
    setStockNewQty(1);
    setFormError('');
    try {
      const q = scope === 'hostel_room' ? `hostel_room_id=${facilityId}` : `other_area_id=${facilityId}`;
      const data = await apiGet(`${CAMPUS_PREFIX}/facility-inventory-items?${q}`);
      setStockItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setStockItems([]);
      setFormError(e.message || 'Failed to load stock');
    }
  };

  const closeStockModal = () => {
    setStockModal(null);
    setStockItems([]);
    setFormError('');
  };

  const submitNewStockItem = async () => {
    if (!stockModal || !isAdmin) return;
    const name = stockNewName.trim();
    if (!name) return;
    setSaving(true);
    try {
      await apiPost(`${CAMPUS_PREFIX}/facility-inventory-items`, {
        facility_scope: stockModal.scope,
        facility_id: stockModal.facilityId,
        name,
        quantity_available: Math.max(0, parseInt(stockNewQty, 10) || 0),
      });
      setStockNewName('');
      setStockNewQty(1);
      await openStockModal(stockModal.scope, stockModal.facilityId, stockModal.title);
    } catch (e) {
      setFormError(e.message || 'Could not add item');
    } finally {
      setSaving(false);
    }
  };

  const patchStockQty = async (itemId, quantity_available) => {
    if (!stockModal) return;
    setSaving(true);
    try {
      await apiPatch(`${CAMPUS_PREFIX}/facility-inventory-items/${itemId}`, { quantity_available });
      await openStockModal(stockModal.scope, stockModal.facilityId, stockModal.title);
    } catch (e) {
      setFormError(e.message || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteStockItem = async (itemId) => {
    if (!isAdmin || !window.confirm('Remove this inventory item?')) return;
    if (!stockModal) return;
    setSaving(true);
    try {
      await apiDelete(`${CAMPUS_PREFIX}/facility-inventory-items/${itemId}`);
      await openStockModal(stockModal.scope, stockModal.facilityId, stockModal.title);
    } catch (e) {
      setFormError(e.message || 'Delete failed');
    } finally {
      setSaving(false);
    }
  };

  const openMenuModal = async (otherAreaId, areaName) => {
    setMenuModal({ otherAreaId, areaName });
    setMenuNew({ meal_slot: 'breakfast', name: '', diet: 'either' });
    setFormError('');
    try {
      const data = await apiGet(
        `${CAMPUS_PREFIX}/dining-areas/${otherAreaId}/menu-items?include_inactive=true`,
      );
      setMenuItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setMenuItems([]);
      setFormError(e.message || 'Failed to load menu');
    }
  };

  const closeMenuModal = () => {
    setMenuModal(null);
    setMenuItems([]);
    setFormError('');
  };

  const submitNewMenuItem = async () => {
    if (!menuModal || !isAdmin) return;
    const name = menuNew.name.trim();
    if (!name) return;
    setSaving(true);
    try {
      await apiPost(`${CAMPUS_PREFIX}/dining-areas/${menuModal.otherAreaId}/menu-items`, {
        meal_slot: menuNew.meal_slot,
        name,
        diet: menuNew.diet,
        active: true,
      });
      setMenuNew({ meal_slot: menuNew.meal_slot, name: '', diet: 'either' });
      const data = await apiGet(
        `${CAMPUS_PREFIX}/dining-areas/${menuModal.otherAreaId}/menu-items?include_inactive=true`,
      );
      setMenuItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setFormError(e.message || 'Could not add menu item');
    } finally {
      setSaving(false);
    }
  };

  const toggleMenuItemActive = async (row) => {
    if (!canEdit || !menuModal) return;
    setSaving(true);
    try {
      await apiPatch(`${CAMPUS_PREFIX}/dining-menu-items/${row.id}`, { active: !row.active });
      const data = await apiGet(
        `${CAMPUS_PREFIX}/dining-areas/${menuModal.otherAreaId}/menu-items?include_inactive=true`,
      );
      setMenuItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setFormError(e.message || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteMenuItem = async (itemId) => {
    if (!isAdmin || !menuModal || !window.confirm('Delete this menu item?')) return;
    setSaving(true);
    try {
      await apiDelete(`${CAMPUS_PREFIX}/dining-menu-items/${itemId}`);
      const data = await apiGet(
        `${CAMPUS_PREFIX}/dining-areas/${menuModal.otherAreaId}/menu-items?include_inactive=true`,
      );
      setMenuItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setFormError(e.message || 'Delete failed');
    } finally {
      setSaving(false);
    }
  };

  const openEditBooking = (b) => {
    const fmt = (iso) => {
      if (!iso) return '';
      const d = new Date(iso);
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };
    setBookEditTarget(b);
    setEditBookingStart(fmt(b.start_time));
    setEditBookingEnd(fmt(b.end_time));
    setFormError('');
  };

  const closeEditBookingModal = () => {
    setBookEditTarget(null);
    setEditBookingStart('');
    setEditBookingEnd('');
  };

  const submitEditBooking = async () => {
    if (!bookEditTarget) return;
    if (!editBookingStart || !editBookingEnd) {
      setFormError('Please select start and end time');
      return;
    }
    const start = new Date(editBookingStart);
    const end = new Date(editBookingEnd);
    if (end <= start) {
      setFormError('End time must be after start time');
      return;
    }
    const durMs = end - start;
    if (bookEditTarget.hostel_room_id) {
      if (durMs < MIN_HOSTEL_BOOKING_MS) {
        setFormError('Hostel bookings must be at least 1 day from start to end.');
        return;
      }
    } else if (durMs < MIN_OTHER_AREA_BOOKING_MS) {
      setFormError('Bookings for this facility must be at least 2 hours from start to end.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await apiPatch(`/bookings/${bookEditTarget.id}/times`, {
        start_time: start.toISOString(),
        end_time: end.toISOString(),
      });
      closeEditBookingModal();
      await loadBookingsSilent();
      if (facilityView === 'bookings') await loadBookings();
    } catch (e) {
      setFormError(e.message || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!deleteConfirm) return;
    setSaving(true);
    setFormError('');
    try {
      if (deleteConfirm.type === 'booking') {
        await apiDelete(`/bookings/${deleteConfirm.id}`);
        setDeleteConfirm(null);
        await loadBookingsSilent();
        if (facilityView === 'bookings') await loadBookings();
        return;
      }
      const pathMap = {
        campus: (id) => `${CAMPUS_PREFIX}/campuses/${id}`,
        buildings: (id) => `${CAMPUS_PREFIX}/buildings/${id}`,
        floors: (id) => `${CAMPUS_PREFIX}/floors/${id}`,
        'hostel-rooms': (id) => `${CAMPUS_PREFIX}/hostel-rooms/${id}`,
        dining: (id) => `${CAMPUS_PREFIX}/other-areas/${id}`,
        sports: (id) => `${CAMPUS_PREFIX}/other-areas/${id}`,
        'academic-spaces': (id) => `${CAMPUS_PREFIX}/other-areas/${id}`,
      };
      await apiDelete(pathMap[deleteConfirm.entity](deleteConfirm.id));
      setDeleteConfirm(null);
      if (facilityView === 'campus') loadCampuses();
      if (facilityView === 'buildings') loadBuildings();
      if (facilityView === 'floors') loadFloors();
      if (facilityView === 'hostel-rooms') loadHostelRooms();
      if (['dining', 'sports', 'academic-spaces'].includes(facilityView)) loadOtherAreas();
    } catch (e) {
      setFormError(e.message || 'Delete failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-container">
        <header className="dashboard-header">
          <span className="dashboard-header-title">SmartCampus</span>
          <div className="dashboard-header-actions">
            <div className="dashboard-profile-wrap" ref={profileRef}>
              <button type="button" className="dashboard-profile-icon-btn" disabled aria-label="Profile"><ProfileIcon /></button>
            </div>
            <button type="button" className="dashboard-header-btn dashboard-header-logout" disabled>Logout</button>
          </div>
        </header>
        <div className="dashboard-main dashboard-main-with-sidebar">
          <div className="dashboard-card"><p className="loading-msg">Loading...</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className={`dashboard-container ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
      <header className="dashboard-header">
        <div className="header-left">
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle Sidebar"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          </button>
          <span className="dashboard-header-title">SmartCampus</span>
        </div>
        <div className="dashboard-header-actions">
          <div className="dashboard-notif-wrap" ref={notifRef}>
            <button
              type="button"
              className="dashboard-notif-btn"
              onClick={() => {
                setNotifOpen((o) => !o);
                if (!notifOpen) loadNotifications();
              }}
              aria-label="Notifications"
              aria-expanded={notifOpen}
            >
              <BellIcon />
              {unreadNotifCount > 0 && <span className="dashboard-notif-badge">{unreadNotifCount > 99 ? '99+' : unreadNotifCount}</span>}
            </button>
          </div>
          <div className="dashboard-profile-wrap" ref={profileRef}>
            <button type="button" className="dashboard-profile-icon-btn" onClick={() => setProfileOpen(!profileOpen)} aria-label="Profile" aria-expanded={profileOpen}>
              <ProfileIcon />
            </button>
            {profileOpen && profile && (
              <div className="dashboard-profile-dropdown">
                <div className="dashboard-profile-dropdown-row"><span className="label">Name</span><span className="value">{profile.name}</span></div>
                <div className="dashboard-profile-dropdown-row"><span className="label">Email</span><span className="value">{profile.email}</span></div>
                <div className="dashboard-profile-dropdown-row"><span className="label">Role</span><span className="value">{profile.role}</span></div>
                {profile.phone_number && <div className="dashboard-profile-dropdown-row"><span className="label">Phone</span><span className="value">{profile.phone_number}</span></div>}
                {canBook && (
                  <>
                    <div className="dashboard-profile-dropdown-row dashboard-profile-eligibility">
                      <span className="label">Year</span>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        className="dashboard-profile-input"
                        value={profileEligibility.year}
                        onChange={(e) => setProfileEligibility({ ...profileEligibility, year: e.target.value })}
                      />
                    </div>
                    <div className="dashboard-profile-dropdown-row dashboard-profile-eligibility">
                      <span className="label">Dept</span>
                      <input
                        type="text"
                        className="dashboard-profile-input"
                        placeholder="e.g. CS"
                        value={profileEligibility.dept}
                        onChange={(e) => setProfileEligibility({ ...profileEligibility, dept: e.target.value })}
                      />
                    </div>
                    <div className="dashboard-profile-dropdown-row dashboard-profile-eligibility">
                      <span className="label">Membership</span>
                      <select
                        className="dashboard-profile-input"
                        value={profileEligibility.tier}
                        onChange={(e) => setProfileEligibility({ ...profileEligibility, tier: e.target.value })}
                      >
                        <option value="basic">basic</option>
                        <option value="standard">standard</option>
                        <option value="premium">premium</option>
                      </select>
                    </div>
                    <div className="dashboard-profile-dropdown-actions">
                      <button
                        type="button"
                        className="facility-btn-book"
                        onClick={async () => {
                          setProfileSaveMsg('');
                          try {
                            const data = await apiPatch('/users/profile', {
                              year_of_study: profileEligibility.year === '' ? null : +profileEligibility.year,
                              department: profileEligibility.dept.trim() || null,
                              membership_tier: profileEligibility.tier,
                            });
                            setProfile(data);
                            setProfileSaveMsg('Saved.');
                          } catch (e) {
                            setProfileSaveMsg(e.message || 'Save failed');
                          }
                        }}
                      >
                        Save eligibility
                      </button>
                    </div>
                    {profileSaveMsg && <p className="facility-modal-hint" style={{ marginTop: 8 }}>{profileSaveMsg}</p>}
                  </>
                )}
              </div>
            )}
          </div>
          <button type="button" className="dashboard-header-btn dashboard-header-logout" onClick={handleLogout}>Logout</button>
        </div>
      </header>

      <div className="dashboard-body">
        <aside className={`dashboard-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          <div className="sidebar-menu-wrap" ref={facilitiesRef}>
            <button type="button" className="sidebar-menu-trigger" onClick={() => setFacilitiesOpen(!facilitiesOpen)} aria-expanded={facilitiesOpen}>
              <span>Facilities</span>
              <span className={`sidebar-chevron ${facilitiesOpen ? 'open' : ''}`}><ChevronDown /></span>
            </button>
            {facilitiesOpen && (
              <ul className="sidebar-dropdown">
                {visibleFacilityMenu.map((item) => (
                  <li key={item.id}>
                    <button type="button" className={`sidebar-dropdown-item ${facilityView === item.id ? 'active' : ''}`} onClick={() => selectFacility(item.id)}>
                      {item.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {canReviewBookings && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'review-bookings' ? 'active' : ''}`} onClick={() => selectFacility('review-bookings')}>
                <span>Review bookings</span>
              </button>
            </div>
          )}
          {canViewIot && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'iot-monitoring' ? 'active' : ''}`} onClick={() => selectFacility('iot-monitoring')}>
                <span>{isSecurity ? 'Occupancy (IoT)' : 'IoT monitoring'}</span>
              </button>
            </div>
          )}
          {canEmergency && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'emergency' ? 'active' : ''}`} onClick={() => selectFacility('emergency')}>
                <span>Emergency response</span>
              </button>
            </div>
          )}
          {canEdit && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'analytics' ? 'active' : ''}`} onClick={() => selectFacility('analytics')}>
                <span>Analytics</span>
              </button>
            </div>
          )}
          {isAdmin && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'user-admin' ? 'active' : ''}`} onClick={() => selectFacility('user-admin')}>
                <span>User management</span>
              </button>
            </div>
          )}
          {canEdit && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'maintenance-schedule' ? 'active' : ''}`} onClick={() => selectFacility('maintenance-schedule')}>
                <span>Maintenance schedule</span>
              </button>
            </div>
          )}
          <div className="sidebar-menu-wrap">
            <button type="button" className={`sidebar-menu-trigger ${facilityView === 'maintenance' ? 'active' : ''}`} onClick={() => selectFacility('maintenance')}>
              <span>Maintenance issue</span>
            </button>
          </div>
          {canBook && (
            <div className="sidebar-menu-wrap">
              <button type="button" className={`sidebar-menu-trigger ${facilityView === 'bookings' ? 'active' : ''}`} onClick={() => selectFacility('bookings')}>
                <span>Bookings</span>
              </button>
            </div>
          )}
        </aside>

        <main className="dashboard-main dashboard-main-with-sidebar">
          {!facilityView && (
            <div className="dashboard-card">
              <h1 className="dashboard-welcome">Welcome{profile?.name ? `, ${profile.name}` : ''}</h1>
              <p className="subtitle">SmartCampus – Intelligent Campus Management System</p>
              <p className="coming-soon">
                {canBook
                  ? 'Select Facilities to book Hostel Rooms, Mess/Dining, Sports, or Academic Spaces, or open Bookings for your reservations.'
                  : 'Select Facilities from the left menu to manage Campus, Buildings, Floors, Hostel Rooms, Mess/Dining, Sports, or Academic Spaces.'}
              </p>
            </div>
          )}

          {facilityView === 'iot-monitoring' && (
            <div className="dashboard-card facility-card iot-dashboard-card dark-card">
              <div className="facility-page-header">
                <h2>{isSecurity ? 'Occupancy monitoring' : 'IoT monitoring'}</h2>
                <button type="button" className="facility-btn-add" onClick={loadIotData} disabled={iotLoading}>
                  {iotLoading ? 'Refreshing…' : 'Refresh'}
                </button>
              </div>
              {isSecurity && (
                <p className="iot-dashboard-hint">
                  Security view: occupancy-class sensors only (including motion/PIR mapped as occupancy). Read-only — no sync or acknowledgements.
                </p>
              )}
              {!isSecurity && (
                <div className="facility-filter-bar iot-filter-bar">
                  <label className="facility-filter-item">
                    <span>Facility type</span>
                    <select value={iotFacilityTypeFilter} onChange={(e) => setIotFacilityTypeFilter(e.target.value)}>
                      {IOT_FACILITY_TYPE_FILTERS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
              {iotSyncWarning && !isSecurity && <div className="facility-error iot-sync-warning">{iotSyncWarning}</div>}
              {iotError && <div className="facility-error">{iotError}</div>}
              {iotSummary && (
                <div className="analytics-stat-grid">
                  <div className="analytics-stat-card">
                    <span className="analytics-stat-label">{isSecurity ? 'Occupancy readings (24h)' : 'Readings (24h)'}</span>
                    <span className="analytics-stat-value">{iotSummary.readings_last_24h ?? '—'}</span>
                  </div>
                  <div className="analytics-stat-card">
                    <span className="analytics-stat-label">{isSecurity ? 'Open occupancy alerts' : 'Open alerts'}</span>
                    <span className="analytics-stat-value">{iotSummary.open_alerts ?? '—'}</span>
                  </div>
                </div>
              )}
              {iotLoading && !iotSummary && <div className="facility-loading">Loading…</div>}
              <h3 className="facility-section-title">{isSecurity ? 'Occupancy readings' : 'Recent readings'}</h3>
              <div className="facility-table-wrap">
                <table className="facility-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      {!isSecurity && <th>Facility type</th>}
                      {!isSecurity && <th>Name / Room No</th>}
                      <th>Sensor</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {iotReadings.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <span className="iot-dot" />
                            {r.timestamp ? new Date(r.timestamp).toLocaleString() : '—'}
                          </div>
                        </td>
                        {!isSecurity && <td>{iotFacilityTypeLabel(r)}</td>}
                        {!isSecurity && (
                          <td>
                            <button
                              type="button"
                              className="facility-link-btn"
                              onClick={() => navigateIoTRowToFacility(r)}
                              title="Open facility page with filters"
                            >
                              {iotNameOrRoomLabel(r)}
                            </button>
                          </td>
                        )}
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <div className="sensor-icon-wrap">
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>
                            </div>
                            {r.sensor_type}
                          </div>
                        </td>
                        <td><strong style={{ color: 'var(--accent)' }}>{r.display_value != null ? r.display_value : r.value}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!iotLoading && iotReadings.length === 0 && <p className="facility-empty">No readings for this filter.</p>}
              <h3 className="facility-section-title">{isSecurity ? 'Occupancy alerts' : 'Sensor alerts'}</h3>
              <div className="facility-table-wrap">
                <table className="facility-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      {!isSecurity && <th>Facility type</th>}
                      {!isSecurity && <th>Facility name / Room no</th>}
                      <th>Sensor</th>
                      <th>Alert</th>
                      <th>Value</th>
                      {!isSecurity && <th>Action</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {iotAlerts.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <span className="iot-dot" style={{ backgroundColor: 'red', boxShadow: '0 0 8px red' }} />
                            {a.triggered_at ? new Date(a.triggered_at).toLocaleString() : '—'}
                          </div>
                        </td>
                        {!isSecurity && <td>{iotFacilityTypeLabel(a)}</td>}
                        {!isSecurity && (
                          <td>
                            <button
                              type="button"
                              className="facility-link-btn"
                              onClick={() => navigateIoTRowToFacility(a)}
                              title="Open facility page with filters"
                            >
                              {iotNameOrRoomLabel(a)}
                            </button>
                          </td>
                        )}
                        <td>{a.sensor_type}</td>
                        <td><span style={{ color: 'red', fontWeight: 'bold' }}>{a.alert_type}</span></td>
                        <td>{iotAlertValueDisplay(a)}</td>
                        {!isSecurity && (
                          <td>
                            {a.status === 'open' ? (
                              <button type="button" className="facility-btn-book" onClick={() => acknowledgeAlert(a.id)}>
                                Acknowledge
                              </button>
                            ) : (
                              <span className="iot-alert-action-label">
                                {a.status === 'acknowledged' ? 'Acknowledged' : 'Resolved'}
                              </span>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!iotLoading && iotAlerts.length === 0 && <p className="facility-empty">No alerts for this filter.</p>}
            </div>
          )}

          {facilityView === 'emergency' && (
            <div className="dashboard-card facility-card emergency-card dark-card">
              <div className="facility-page-header">
                <h2>Emergency Response</h2>
              </div>

              <div className="emergency-content-wrap">
                <div className="emergency-form-card">
                  <p className="emergency-subtitle">
                    Broadcast an urgent alert to selected user roles across the campus.
                  </p>
                  {emergencyError && <div className="facility-error">{emergencyError}</div>}
                  {emergencyOk && <div className="facility-modal-hint">{emergencyOk}</div>}
                  <div className="facility-form">
                    <label>
                      Target user role
                      <select value={emergencyTargetRole} onChange={(e) => setEmergencyTargetRole(e.target.value)}>
                        {EMERGENCY_TARGET_ROLE_OPTIONS.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Description / message
                      <textarea
                        value={emergencyDesc}
                        onChange={(e) => setEmergencyDesc(e.target.value)}
                        rows={5}
                        placeholder="Describe the situation and any actions recipients should take."
                      />
                    </label>
                    <button type="button" className="facility-btn-save emergency-send-btn" onClick={submitEmergencyBroadcast} disabled={saving}>
                      {saving ? 'Sending…' : 'Send Alert'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {facilityView === 'maintenance' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Maintenance issue</h2>
                <button type="button" className="facility-btn-add" onClick={() => { setMtFormOpen(true); setMaintenanceError(''); }}>
                  Report maintenance issue
                </button>
              </div>
              <p className="iot-dashboard-hint">Submit a maintenance issue for broken assets (e.g. leaking tap). Upload photos. {canEdit ? 'Facility team can update status.' : ''}</p>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Status</span>
                  <select value={mtStatusFilter} onChange={(e) => setMtStatusFilter(e.target.value)}>
                    <option value="all">All</option>
                    <option value="open">Open</option>
                    <option value="in_progress">In progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                </label>
              </div>
              {maintenanceError && <div className="facility-error">{maintenanceError}</div>}
              {maintenanceLoading ? (
                <div className="facility-loading">Loading…</div>
              ) : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Issue</th>
                        <th>Location</th>
                        <th>Status</th>
                        <th>Reporter</th>
                        <th>Photos</th>
                        {canEdit && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {maintenanceTickets.map((t) => (
                        <tr key={t.id}>
                          <td>{t.id}</td>
                          <td>
                            <button
                              type="button"
                              className="facility-link-btn"
                              onClick={() => setMtIssueViewModal({ title: t.title, description: t.description })}
                            >
                              {t.title}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="facility-link-btn"
                              onClick={() => setMtLocationViewModal({ label: t.facility_label, detail: t.facility_detail })}
                            >
                              {t.facility_label}
                            </button>
                          </td>
                          <td>{t.status}</td>
                          <td>{t.reporter_name}</td>
                          <td className="mt-photo-cell">
                            {(t.photo_urls || []).map((u) => (
                              <a key={u} href={`${API_BASE}${u}`} target="_blank" rel="noopener noreferrer" className="mt-photo-thumb-link">
                                <img src={`${API_BASE}${u}`} alt="" className="mt-photo-thumb" />
                              </a>
                            ))}
                            {(!t.photo_urls || !t.photo_urls.length) && <span className="facility-muted">—</span>}
                          </td>
                          {canEdit && (
                            <td>
                              <select
                                value={t.status}
                                onChange={(e) => updateMaintenanceStatus(t.id, e.target.value)}
                                className="mt-status-select"
                                aria-label={`Status for maintenance issue ${t.id}`}
                              >
                                <option value="open">open</option>
                                <option value="in_progress">in_progress</option>
                                <option value="resolved">resolved</option>
                                <option value="closed">closed</option>
                              </select>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!maintenanceLoading && maintenanceTickets.length === 0 && <p className="facility-empty">No maintenance issues yet.</p>}
            </div>
          )}

          {facilityView === 'analytics' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Analytics</h2>
                <button type="button" className="facility-btn-add" onClick={loadAnalytics} disabled={analyticsLoading}>
                  {analyticsLoading ? 'Loading…' : 'Refresh'}
                </button>
              </div>
              {analyticsError && <div className="facility-error">{analyticsError}</div>}
              {analyticsLoading && !analytics && <div className="facility-loading">Loading…</div>}
              {analytics && (
                <>
                  <div className="analytics-stat-grid">
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Total bookings</span>
                      <span className="analytics-stat-value">{analytics.bookings_total}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Hostel bookings</span>
                      <span className="analytics-stat-value">{analytics.hostel_booking_count}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Other area bookings</span>
                      <span className="analytics-stat-value">{analytics.other_area_booking_count}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Hostel rooms</span>
                      <span className="analytics-stat-value">{analytics.hostel_rooms_count}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Other areas</span>
                      <span className="analytics-stat-value">{analytics.other_areas_count}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Sensor readings</span>
                      <span className="analytics-stat-value">{analytics.sensor_readings}</span>
                    </div>
                    <div className="analytics-stat-card">
                      <span className="analytics-stat-label">Open sensor alerts</span>
                      <span className="analytics-stat-value">{analytics.open_sensor_alerts}</span>
                    </div>
                  </div>
                  <h3 className="facility-section-title">Bookings by status</h3>
                  <ul className="analytics-status-list">
                    {analytics.bookings_by_status &&
                      Object.entries(analytics.bookings_by_status).map(([k, v]) => (
                        <li key={k}>
                          <span className="analytics-status-key">{k}</span>
                          <span className="analytics-status-val">{v}</span>
                        </li>
                      ))}
                  </ul>
                </>
              )}
            </div>
          )}

          {facilityView === 'user-admin' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>User management</h2>
                <button type="button" className="facility-btn-add" onClick={loadAdminUsers} disabled={adminUsersLoading}>
                  {adminUsersLoading ? 'Loading…' : 'Refresh'}
                </button>
              </div>
              <p className="iot-dashboard-hint">List all accounts, change roles, and activate or deactivate users. You cannot deactivate yourself or remove the last active administrator.</p>
              {adminUsersError && <div className="facility-error">{adminUsersError}</div>}
              {adminUsersLoading ? (
                <div className="facility-loading">Loading…</div>
              ) : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Active</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {adminUsers.map((u) => {
                        const d = userDrafts[u.id] || { role: u.role, is_active: u.is_active !== false };
                        return (
                          <tr key={u.id}>
                            <td>{u.id}</td>
                            <td>{u.name}</td>
                            <td>{u.email}</td>
                            <td>
                              <select
                                value={d.role}
                                onChange={(e) =>
                                  setUserDrafts((prev) => ({
                                    ...prev,
                                    [u.id]: { ...d, role: e.target.value },
                                  }))
                                }
                                className="mt-status-select"
                                aria-label={`Role for user ${u.id}`}
                              >
                                {USER_ROLE_OPTIONS.map((r) => (
                                  <option key={r} value={r}>
                                    {r}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <label className="facility-form-check">
                                <input
                                  type="checkbox"
                                  checked={d.is_active}
                                  onChange={(e) =>
                                    setUserDrafts((prev) => ({
                                      ...prev,
                                      [u.id]: { ...d, is_active: e.target.checked },
                                    }))
                                  }
                                />
                              </label>
                            </td>
                            <td>
                              <button
                                type="button"
                                className="facility-btn-book"
                                disabled={saving}
                                onClick={() =>
                                  patchAdminUser(u.id, { role: d.role, is_active: d.is_active })
                                }
                              >
                                Save
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              {!adminUsersLoading && adminUsers.length === 0 && <p className="facility-empty">No users found.</p>}
            </div>
          )}

          {facilityView === 'maintenance-schedule' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Maintenance schedule</h2>
                <button
                  type="button"
                  className="facility-btn-add"
                  onClick={() => {
                    setSchedFormOpen(true);
                    setMaintSchedError('');
                  }}
                >
                  Add schedule
                </button>
              </div>
              <p className="iot-dashboard-hint">
                Plan maintenance windows for hostel rooms or other facilities. Facility managers and admins can create and update schedules.
              </p>
              {maintSchedError && <div className="facility-error">{maintSchedError}</div>}
              {maintSchedLoading ? (
                <div className="facility-loading">Loading…</div>
              ) : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Location</th>
                        <th>Start</th>
                        <th>End</th>
                        <th>Status</th>
                        <th>Created by</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {maintSchedules.map((s) => (
                        <tr key={s.id}>
                          <td>{s.id}</td>
                          <td>{s.title}</td>
                          <td>
                            <button
                              type="button"
                              className="facility-link-btn"
                              onClick={() => navigateMaintScheduleToFacility(s)}
                              title="Open this facility in Facilities"
                            >
                              {s.facility_label}
                            </button>
                          </td>
                          <td>{s.scheduled_start ? new Date(s.scheduled_start).toLocaleString() : '—'}</td>
                          <td>{s.scheduled_end ? new Date(s.scheduled_end).toLocaleString() : '—'}</td>
                          <td>
                            <select
                              value={s.status}
                              onChange={(e) => patchMaintScheduleStatus(s.id, e.target.value)}
                              className="mt-status-select"
                              aria-label={`Schedule status ${s.id}`}
                            >
                              <option value="scheduled">scheduled</option>
                              <option value="in_progress">in_progress</option>
                              <option value="completed">completed</option>
                              <option value="cancelled">cancelled</option>
                            </select>
                          </td>
                          <td>{s.created_by_name}</td>
                          <td>
                            <button type="button" className="facility-btn-delete" onClick={() => deleteMaintSchedule(s.id)}>
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!maintSchedLoading && maintSchedules.length === 0 && <p className="facility-empty">No scheduled maintenance yet.</p>}
            </div>
          )}

          {facilityView === 'campus' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Campus</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('campus')}>+ Create Campus</button>}
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Name</th><th>Location</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {campuses.map((r) => (
                        <tr key={r.id}><td>{r.name}</td><td>{r.location ?? '—'}</td>
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('campus', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'campus', id: r.id, name: r.name })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && campuses.length === 0 && <p className="facility-empty">No campuses yet.</p>}
            </div>
          )}

          {facilityView === 'buildings' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Buildings</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('buildings')}>+ Create Building</button>}
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Filter by Campus</span>
                  <select value={buildingsFilterCampus} onChange={(e) => setBuildingsFilterCampus(e.target.value)}>
                    <option value="">All</option>
                    {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by name..." value={buildingsSearch} onChange={(e) => setBuildingsSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Name</th><th>Campus</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {filteredBuildings.map((r) => (
                        <tr key={r.id}><td>{r.name}</td><td>{campuses.find((c) => c.id === r.campus_id)?.name ?? r.campus_id}</td>
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('buildings', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'buildings', id: r.id, name: r.name })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && filteredBuildings.length === 0 && <p className="facility-empty">No buildings match your filters.</p>}
            </div>
          )}

          {facilityView === 'floors' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Floors</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('floors')}>+ Create Floor</button>}
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Filter by Building</span>
                  <select value={floorsFilterBuilding} onChange={(e) => setFloorsFilterBuilding(e.target.value)}>
                    <option value="">All</option>
                    {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by floor no..." value={floorsSearch} onChange={(e) => setFloorsSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Building</th><th>Floor No</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {filteredFloors.map((r) => (
                        <tr key={r.id}><td>{buildings.find((b) => b.id === r.building_id)?.name ?? r.building_id}</td><td>{r.floor_no}</td>
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('floors', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'floors', id: r.id, name: `Floor ${r.floor_no}` })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && filteredFloors.length === 0 && <p className="facility-empty">No floors match your filters.</p>}
            </div>
          )}

          {facilityView === 'hostel-rooms' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Hostel Rooms</h2>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {canEdit && <button type="button" className="facility-btn-add" style={{ background: '#6366f1' }} onClick={runAllocationEngine} disabled={saving}>Run Hostel Allocation Engine</button>}
                  {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('hostel-rooms')}>+ Create Hostel Room</button>}
                </div>
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Building</span>
                  <select value={hostelFilterBuilding} onChange={(e) => setHostelFilterBuilding(e.target.value)}>
                    <option value="">All</option>
                    {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Floor</span>
                  <select value={hostelFilterFloor} onChange={(e) => setHostelFilterFloor(e.target.value)}>
                    <option value="">All</option>
                    {floors.map((f) => <option key={f.id} value={f.id}>{f.name || `Floor ${f.floor_no}`}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Facility Type (Men&apos;s / Ladies&apos;)</span>
                  <select value={hostelFilterFacilityType} onChange={(e) => setHostelFilterFacilityType(e.target.value)}>
                    <option value="">All</option>
                    {hostelFacilityTypeOptions.map((ft) => <option key={ft.id} value={ft.id}>{ft.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by room no..." value={hostelSearch} onChange={(e) => setHostelSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Room No</th><th>Type</th><th>Facility Type</th><th>Capacity</th><th>Inmates</th>{canBook && <th>Book</th>}{canEdit && <th>Stock</th>}{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {filteredHostelRooms.map((r) => (
                        <tr key={r.id}><td>{r.roomno}</td><td>{r.room_type}</td><td>{facilityTypes.find((ft) => ft.id === r.facility_type_id)?.name ?? r.facility_type_id}</td><td>{r.room_capacity}</td><td>
                          <button
                            type="button"
                            className="facility-btn-edit"
                            onClick={() => openHostelOccupancyModal(r.id, r.roomno)}
                          >
                            View
                          </button>
                        </td>
                          {renderBookCell('hostel_room', r.id, r.roomno, 'hostel_room')}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openStockModal('hostel_room', r.id, r.roomno)}>Stock</button></td>}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('hostel-rooms', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'hostel-rooms', id: r.id, name: r.roomno })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && filteredHostelRooms.length === 0 && <p className="facility-empty">No hostel rooms match your filters.</p>}
            </div>
          )}

          {facilityView === 'review-bookings' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Review bookings</h2>
              </div>
              <p className="facility-modal-hint">Queue order: VIP first, then by request time. Only Staff can request VIP when booking (non-hostel). Overlapping normal bookings are rejected and users are notified only after Admin or Facility Manager accepts that VIP request.</p>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Show</span>
                  <select value={reviewBookingFilter} onChange={(e) => setReviewBookingFilter(e.target.value)}>
                    <option value="pending">Not reviewed (pending)</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                    <option value="all">All</option>
                  </select>
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Priority</th><th>Requested</th><th>User</th><th>Start</th><th>End</th><th>Facility room no/ name</th><th>Inventories</th><th>Status</th></tr></thead>
                    <tbody>
                      {bookings.map((b) => (
                        <tr key={b.id}>
                          <td>{b.priority === 'vip' ? 'VIP' : 'Normal'}</td>
                          <td>{b.created_at ? new Date(b.created_at).toLocaleString() : '—'}</td>
                          <td>
                            {b.user ? (
                              <button type="button" className="facility-link-btn" onClick={() => setUserDetailModal(b.user)}>
                                {b.user.name}
                              </button>
                            ) : (
                              <span className="facility-muted">#{b.user_id}</span>
                            )}
                          </td>
                          <td>{b.start_time ? new Date(b.start_time).toLocaleString() : '—'}</td>
                          <td>{b.end_time ? new Date(b.end_time).toLocaleString() : '—'}</td>
                          <td>
                              <button type="button" className="facility-link-btn" onClick={() => navigateBookingToFacility(b)}>
                                {b.hostel_room_id ? (hostelRooms.find(r => r.id === b.hostel_room_id)?.roomno || `Room ${b.hostel_room_id}`) : b.other_area_id ? (otherAreas.find(a => a.id === b.other_area_id)?.name || `Area ${b.other_area_id}`) : '—'}
                              </button>
                           </td>
                          <td>{formatInventories(b)}</td>
                          <td>{b.status === 'accepted' ? 'Accepted' : b.status === 'rejected' ? 'Rejected' : 'Pending'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && bookings.length === 0 && <p className="facility-empty">No bookings in this view.</p>}
            </div>
          )}

          {facilityView === 'bookings' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>My Bookings</h2>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <>
                  <h3 className="facility-section-title">Accepted</h3>
                  <div className="facility-table-wrap">
                    <table className="facility-table">
                      <thead><tr><th>Start</th><th>End</th><th>Resource</th><th>Inventories</th><th>Actions</th></tr></thead>
                      <tbody>
                        {bookings.filter((b) => b.status === 'accepted').map((b) => (
                          <tr key={b.id}>
                            <td>{b.start_time ? new Date(b.start_time).toLocaleString() : '—'}</td>
                            <td>{b.end_time ? new Date(b.end_time).toLocaleString() : '—'}</td>
                            <td>
                              <button type="button" className="facility-link-btn" onClick={() => navigateBookingToFacility(b)}>
                                {b.hostel_room_id ? (hostelRooms.find(r => r.id === b.hostel_room_id)?.roomno || `Room ${b.hostel_room_id}`) : b.other_area_id ? (otherAreas.find(a => a.id === b.other_area_id)?.name || `Area ${b.other_area_id}`) : '—'}
                              </button>
                            </td>
                            <td>{formatInventories(b)}</td>
                            <td>
                              <button type="button" className="facility-btn-edit" onClick={() => openEditBooking(b)}>Modify</button>
                              <button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ type: 'booking', id: b.id, name: 'booking' })}>Cancel</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {bookings.filter((b) => b.status === 'accepted').length === 0 && <p className="facility-empty">No accepted bookings.</p>}
                  <h3 className="facility-section-title">Waiting for approval</h3>
                  <div className="facility-table-wrap">
                    <table className="facility-table">
                      <thead><tr><th>Start</th><th>End</th><th>Resource</th><th>Inventories</th><th>Actions</th></tr></thead>
                      <tbody>
                        {bookings.filter((b) => b.status === 'pending').map((b) => (
                          <tr key={b.id}>
                            <td>{b.start_time ? new Date(b.start_time).toLocaleString() : '—'}</td>
                            <td>{b.end_time ? new Date(b.end_time).toLocaleString() : '—'}</td>
                            <td>
                              <button type="button" className="facility-link-btn" onClick={() => navigateBookingToFacility(b)}>
                                {b.hostel_room_id ? (hostelRooms.find(r => r.id === b.hostel_room_id)?.roomno || `Room ${b.hostel_room_id}`) : b.other_area_id ? (otherAreas.find(a => a.id === b.other_area_id)?.name || `Area ${b.other_area_id}`) : '—'}
                              </button>
                            </td>
                            <td>{formatInventories(b)}</td>
                            <td>
                              <button type="button" className="facility-btn-edit" onClick={() => openEditBooking(b)}>Modify</button>
                              <button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ type: 'booking', id: b.id, name: 'booking' })}>Cancel</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {bookings.filter((b) => b.status === 'pending').length === 0 && <p className="facility-empty">No bookings waiting for approval.</p>}
                  <h3 className="facility-section-title">Rejected</h3>
                  <div className="facility-table-wrap">
                    <table className="facility-table">
                      <thead><tr><th>Start</th><th>End</th><th>Resource</th><th>Inventories</th><th>Actions</th></tr></thead>
                      <tbody>
                        {bookings.filter((b) => b.status === 'rejected').map((b) => (
                          <tr key={b.id}>
                            <td>{b.start_time ? new Date(b.start_time).toLocaleString() : '—'}</td>
                            <td>{b.end_time ? new Date(b.end_time).toLocaleString() : '—'}</td>
                            <td>
                              <button type="button" className="facility-link-btn" onClick={() => navigateBookingToFacility(b)}>
                                {b.hostel_room_id ? (hostelRooms.find(r => r.id === b.hostel_room_id)?.roomno || `Room ${b.hostel_room_id}`) : b.other_area_id ? (otherAreas.find(a => a.id === b.other_area_id)?.name || `Area ${b.other_area_id}`) : '—'}
                              </button>
                            </td>
                            <td>{formatInventories(b)}</td>
                            <td>
                              <button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ type: 'booking', id: b.id, name: 'booking' })}>Remove</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {bookings.filter((b) => b.status === 'rejected').length === 0 && <p className="facility-empty">No rejected bookings.</p>}
                </>
              )}
            </div>
          )}

          {facilityView === 'dining' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Mess / Dining</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('dining')}>+ Create</button>}
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Filter by Building</span>
                  <select value={otherTypeFilterBuilding} onChange={(e) => setOtherTypeFilterBuilding(e.target.value)}>
                    <option value="">All</option>
                    {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by name..." value={otherTypeSearch} onChange={(e) => setOtherTypeSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Name</th><th>Building</th><th>Floor</th><th>Capacity</th><th>Active</th>{canBook && <th>Book</th>}{canEdit && <th>Menu</th>}{canEdit && <th>Stock</th>}{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {getOtherAreasByType('dining').map((r) => (
                        <tr key={r.id}><td>{r.name}</td><td>{buildings.find((b) => b.id === r.building_id)?.name ?? r.building_id}</td><td>{floors.find((f) => f.id === r.floor_id) ? `Floor ${floors.find((f) => f.id === r.floor_id).floor_no}` : r.floor_id}</td><td>{r.capacity ?? '—'}</td><td>{r.active ? 'Yes' : 'No'}</td>
                          {renderBookCell('other_area', r.id, r.name, 'dining')}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openMenuModal(r.id, r.name)}>Menu</button></td>}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openStockModal('other_area', r.id, r.name)}>Stock</button></td>}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('dining', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'dining', id: r.id, name: r.name })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && getOtherAreasByType('dining').length === 0 && <p className="facility-empty">No dining facilities match your filters.</p>}
            </div>
          )}

          {facilityView === 'sports' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Sports</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('sports')}>+ Create</button>}
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Filter by Building</span>
                  <select value={otherTypeFilterBuilding} onChange={(e) => setOtherTypeFilterBuilding(e.target.value)}>
                    <option value="">All</option>
                    {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by name..." value={otherTypeSearch} onChange={(e) => setOtherTypeSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Name</th><th>Building</th><th>Floor</th><th>Capacity</th><th>Active</th>{canBook && <th>Book</th>}{canEdit && <th>Stock</th>}{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {getOtherAreasByType('sports').map((r) => (
                        <tr key={r.id}><td>{r.name}</td><td>{buildings.find((b) => b.id === r.building_id)?.name ?? r.building_id}</td><td>{floors.find((f) => f.id === r.floor_id) ? `Floor ${floors.find((f) => f.id === r.floor_id).floor_no}` : r.floor_id}</td><td>{r.capacity ?? '—'}</td><td>{r.active ? 'Yes' : 'No'}</td>
                          {renderBookCell('other_area', r.id, r.name, 'sports')}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openStockModal('other_area', r.id, r.name)}>Stock</button></td>}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('sports', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'sports', id: r.id, name: r.name })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && getOtherAreasByType('sports').length === 0 && <p className="facility-empty">No sports facilities match your filters.</p>}
            </div>
          )}

          {facilityView === 'academic-spaces' && (
            <div className="dashboard-card facility-card dark-card">
              <div className="facility-page-header">
                <h2>Academic Spaces</h2>
                {isAdmin && <button type="button" className="facility-btn-add" onClick={() => openAdd('academic-spaces')}>+ Create</button>}
              </div>
              <div className="facility-filter-bar">
                <label className="facility-filter-item">
                  <span>Filter by Building</span>
                  <select value={otherTypeFilterBuilding} onChange={(e) => setOtherTypeFilterBuilding(e.target.value)}>
                    <option value="">All</option>
                    {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </label>
                <label className="facility-filter-item">
                  <span>Search</span>
                  <input type="text" placeholder="Search by name..." value={otherTypeSearch} onChange={(e) => setOtherTypeSearch(e.target.value)} />
                </label>
              </div>
              {error && <div className="facility-error">{error}</div>}
              {formError && <div className="facility-error">{formError}</div>}
              {listLoading ? <div className="facility-loading">Loading...</div> : (
                <div className="facility-table-wrap">
                  <table className="facility-table">
                    <thead><tr><th>Name</th><th>Building</th><th>Floor</th><th>Capacity</th><th>Active</th>{canBook && <th>Book</th>}{canEdit && <th>Stock</th>}{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                    <tbody>
                      {getOtherAreasByType('academic-spaces').map((r) => (
                        <tr key={r.id}><td>{r.name}</td><td>{buildings.find((b) => b.id === r.building_id)?.name ?? r.building_id}</td><td>{floors.find((f) => f.id === r.floor_id) ? `Floor ${floors.find((f) => f.id === r.floor_id).floor_no}` : r.floor_id}</td><td>{r.capacity ?? '—'}</td><td>{r.active ? 'Yes' : 'No'}</td>
                          {renderBookCell('other_area', r.id, r.name, 'academic')}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openStockModal('other_area', r.id, r.name)}>Stock</button></td>}
                          {canEdit && <td><button type="button" className="facility-btn-edit" onClick={() => openEdit('academic-spaces', r)}>Edit</button></td>}
                          {isAdmin && <td><button type="button" className="facility-btn-delete" onClick={() => setDeleteConfirm({ entity: 'academic-spaces', id: r.id, name: r.name })}>Delete</button></td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!listLoading && getOtherAreasByType('academic-spaces').length === 0 && <p className="facility-empty">No academic spaces match your filters.</p>}
            </div>
          )}
        </main>
      </div>

      {/* Add/Edit Modal */}
      {modal && (
        <div className="facility-modal-overlay" onClick={closeModal}>
          <div className="facility-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{modal.type === 'add' ? 'Create' : 'Edit'} {modal.entity === 'campus' ? 'Campus' : modal.entity === 'buildings' ? 'Building' : modal.entity === 'floors' ? 'Floor' : modal.entity === 'hostel-rooms' ? 'Hostel Room' : modal.entity === 'dining' ? 'Mess/Dining' : modal.entity === 'sports' ? 'Sports' : 'Academic Space'}</h3>
            {modal.entity === 'campus' && (
              <div className="facility-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Location <input value={modal.data.location || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, location: e.target.value } })} /></label>
              </div>
            )}
            {modal.entity === 'buildings' && (
              <div className="facility-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Campus <select value={modal.data.campus_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, campus_id: +e.target.value } })}>
                  {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select></label>
              </div>
            )}
            {modal.entity === 'floors' && (
              <div className="facility-form">
                <label>Building <select value={modal.data.building_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, building_id: +e.target.value } })}>
                  {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select></label>
                <label>Floor No <input type="number" value={modal.data.floor_no ?? ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, floor_no: +e.target.value || 0 } })} /></label>
              </div>
            )}
            {modal.entity === 'hostel-rooms' && (
              <div className="facility-form">
                <label>Room No <input value={modal.data.roomno || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, roomno: e.target.value } })} /></label>
                <label>Room Type <select value={modal.data.room_type || 'Single'} onChange={(e) => setModal({ ...modal, data: { ...modal.data, room_type: e.target.value } })}>
                  {ROOM_TYPES.map((n) => <option key={n} value={n}>{n}</option>)}
                </select></label>
                <label>Facility Type (Men&apos;s / Ladies&apos;){' '}
                  <select
                    value={modal.data.facility_type_id || ''}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, facility_type_id: +e.target.value } })}
                  >
                    {hostelFacilityTypeOptions.map((ft) => <option key={ft.id} value={ft.id}>{ft.name}</option>)}
                  </select>
                </label>
                <label>Building <select value={modal.data.building_id ?? ''} onChange={(e) => { const v = e.target.value; const bid = v ? +v : null; const floorOpts = bid ? floors.filter((f) => f.building_id === bid) : []; setModal({ ...modal, data: { ...modal.data, building_id: bid, floor_id: floorOpts[0]?.id || null } }); }}>
                  <option value="">—</option>
                  {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select></label>
                <label>Floor <select value={modal.data.floor_id ?? ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, floor_id: e.target.value ? +e.target.value : null } })}>
                  <option value="">—</option>
                  {(modal.data.building_id ? floors.filter((f) => f.building_id === modal.data.building_id) : floors).map((f) => <option key={f.id} value={f.id}>Floor {f.floor_no}</option>)}
                </select></label>
                <label>Room Capacity <input type="number" value={modal.data.room_capacity ?? 1} onChange={(e) => setModal({ ...modal, data: { ...modal.data, room_capacity: +e.target.value || 1 } })} /></label>
                <label className="facility-form-block">
                  Minimum Year of Study (Optional)
                  <select
                    className="mt-status-select"
                    value={modal.data.eligReqYear || ''}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, eligReqYear: e.target.value } })}
                  >
                    <option value="">Any Year</option>
                    <option value="1">1st Year</option>
                    <option value="2">2nd Year</option>
                    <option value="3">3rd Year</option>
                    <option value="4">4th Year</option>
                    <option value="5">5th Year</option>
                  </select>
                </label>
                <label className="facility-form-block">
                  Allowed Department (Optional)
                  <select
                    className="mt-status-select"
                    value={modal.data.eligReqDept || ''}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, eligReqDept: e.target.value } })}
                  >
                    <option value="">Any Department</option>
                    <option value="Computer Science">Computer Science</option>
                    <option value="Electronics & Communication">Electronics & Communication</option>
                    <option value="Electrical">Electrical</option>
                    <option value="Mechanical">Mechanical</option>
                    <option value="Civil">Civil</option>
                    <option value="Information Technology">Information Technology</option>
                    <option value="Bio-Technology">Bio-Technology</option>
                  </select>
                </label>
                <p className="facility-modal-hint">Use the Stock column on the hostel list to define bookable items (chairs, desks, …) and quantities.</p>
                <label className="facility-form-check"><input type="checkbox" checked={!!modal.data.staff_only} onChange={(e) => setModal({ ...modal, data: { ...modal.data, staff_only: e.target.checked } })} /> Staff Only (Students cannot book)</label>
              </div>
            )}
            {['dining', 'sports', 'academic-spaces'].includes(modal.entity) && (
              <div className="facility-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Building <select value={modal.data.building_id || ''} onChange={(e) => { const bid = +e.target.value; const floorOpts = floors.filter((f) => f.building_id === bid); setModal({ ...modal, data: { ...modal.data, building_id: bid, floor_id: floorOpts[0]?.id || 0 } }); }}>
                  {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select></label>
                <label>Floor <select value={modal.data.floor_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, floor_id: +e.target.value } })}>
                  {floors.filter((f) => f.building_id === modal.data.building_id).map((f) => <option key={f.id} value={f.id}>Floor {f.floor_no}</option>)}
                </select></label>
                <label>Capacity <input type="number" value={modal.data.capacity ?? ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, capacity: e.target.value ? +e.target.value : null } })} placeholder="Optional" /></label>
                <label className="facility-form-check"><input type="checkbox" checked={!!modal.data.active} onChange={(e) => setModal({ ...modal, data: { ...modal.data, active: e.target.checked } })} /> Active</label>
                <label className="facility-form-check"><input type="checkbox" checked={!!modal.data.staff_only} onChange={(e) => setModal({ ...modal, data: { ...modal.data, staff_only: e.target.checked } })} /> Staff Only</label>
                <label className="facility-form-block">
                  Minimum Year of Study (Optional)
                  <select
                    className="mt-status-select"
                    value={modal.data.eligReqYear || ''}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, eligReqYear: e.target.value } })}
                  >
                    <option value="">Any Year</option>
                    <option value="1">1st Year</option>
                    <option value="2">2nd Year</option>
                    <option value="3">3rd Year</option>
                    <option value="4">4th Year</option>
                    <option value="5">5th Year</option>
                  </select>
                </label>
                <label className="facility-form-block">
                  Allowed Department (Optional)
                  <select
                    className="mt-status-select"
                    value={modal.data.eligReqDept || ''}
                    onChange={(e) => setModal({ ...modal, data: { ...modal.data, eligReqDept: e.target.value } })}
                  >
                    <option value="">Any Department</option>
                    <option value="Computer Science">Computer Science</option>
                    <option value="Electronics & Communication">Electronics & Communication</option>
                    <option value="Electrical">Electrical</option>
                    <option value="Mechanical">Mechanical</option>
                    <option value="Civil">Civil</option>
                    <option value="Information Technology">Information Technology</option>
                    <option value="Bio-Technology">Bio-Technology</option>
                  </select>
                </label>
                <p className="facility-modal-hint">Manage mess menus from the Menu column (dining only). Use Stock on the facility list for bookable inventory.</p>
              </div>
            )}
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={closeModal}>Cancel</button>
              <button type="button" className="facility-btn-save" onClick={saveModal} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
            </div>
          </div>
        </div>
      )}

      {bookTarget && (
        <div className="facility-modal-overlay" onClick={closeBookModal}>
          <div className="facility-modal facility-modal-booking" onClick={(e) => e.stopPropagation()}>
            <h3>Book: {bookTarget.name}</h3>
            {FACILITY_PREVIEW_IMAGES[bookTarget.facilityKey] && (
              <div className="facility-book-preview-wrap">
                <img src={FACILITY_PREVIEW_IMAGES[bookTarget.facilityKey]} alt="" className="facility-book-preview-img" />
              </div>
            )}
            {formError && <div className="facility-error">{formError}</div>}
            <p className="facility-modal-hint">
              {bookTarget.type === 'hostel_room'
                ? 'Minimum booking length: 1 full day (24 hours) from start to end.'
                : 'Minimum booking length: 2 hours from start to end.'}
            </p>
            {bookTarget.type === 'hostel_room' && hostelPreview && (
              <div className="facility-hostel-preview">
                <span className="facility-meal-label">Your dates</span>
                <p className="facility-modal-hint">
                  Room capacity {hostelPreview.room_capacity} · Other bookings in this window {hostelPreview.overlapping_booking_count} · Beds left {hostelPreview.slots_remaining}
                </p>
              </div>
            )}
            {bookingMaintConflictWarning && <div className="facility-error">{bookingMaintConflictWarning}</div>}
            <div className="facility-form">
              <label>Start time <input type="datetime-local" value={bookingStart} onChange={(e) => setBookingStart(e.target.value)} /></label>
              <label>End time <input type="datetime-local" value={bookingEnd} onChange={(e) => setBookingEnd(e.target.value)} /></label>
              {bookTarget.type !== 'hostel_room' && isStaff && (
                <label className="facility-form-check facility-vip-booking-check">
                  <input
                    type="checkbox"
                    checked={bookingRequestVip}
                    onChange={(e) => setBookingRequestVip(e.target.checked)}
                  />
                  <span>
                    VIP booking (Staff only) — you can pick a time that overlaps existing bookings; those bookings stay until Admin or Facility Manager accepts your VIP request, then they are rejected and those users are notified. Your request is listed at the top of the review queue.
                  </span>
                </label>
              )}
              {bookTarget.facilityKey === 'dining' && (
                <>
                  <label>
                    Meal time{' '}
                    <select
                      value={bookingMealSlot}
                      onChange={(e) => {
                        setBookingMealSlot(e.target.value);
                        setBookingMenuIds([]);
                      }}
                    >
                      <option value="">— Select —</option>
                      {MEAL_SLOTS.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </label>
                  <div className="facility-meal-choice">
                    <span className="facility-meal-label">Diet (filters menu)</span>
                    <label className="facility-meal-option">
                      <input
                        type="radio"
                        name="meal_pref"
                        value=""
                        checked={!bookingMealPreference}
                        onChange={() => {
                          setBookingMealPreference('');
                          setBookingMenuIds([]);
                        }}
                      />
                      Any — show all items
                    </label>
                    <label className="facility-meal-option">
                      <input
                        type="radio"
                        name="meal_pref"
                        value="veg"
                        checked={bookingMealPreference === 'veg'}
                        onChange={() => {
                          setBookingMealPreference('veg');
                          setBookingMenuIds([]);
                        }}
                      />
                      Veg only
                    </label>
                    <label className="facility-meal-option">
                      <input
                        type="radio"
                        name="meal_pref"
                        value="non_veg"
                        checked={bookingMealPreference === 'non_veg'}
                        onChange={() => {
                          setBookingMealPreference('non_veg');
                          setBookingMenuIds([]);
                        }}
                      />
                      Non-veg only
                    </label>
                  </div>
                  {bookingMealSlot && (
                    <div className="facility-meal-choice">
                      <span className="facility-meal-label">Menu choices</span>
                      {bookingMenuOptions.length === 0 && (
                        <p className="facility-modal-hint">
                          No items for this slot
                          {bookingMealPreference === 'veg' ? ' (veg)' : bookingMealPreference === 'non_veg' ? ' (non-veg)' : ''}. Try another diet filter or ask admin to add menu items.
                        </p>
                      )}
                      {bookingMenuOptions.map((m) => (
                        <label key={m.id} className="facility-meal-option">
                          <input
                            type="checkbox"
                            checked={bookingMenuIds.includes(m.id)}
                            onChange={() => {
                              setBookingMenuIds((prev) => (prev.includes(m.id) ? prev.filter((x) => x !== m.id) : [...prev, m.id]));
                            }}
                          />
                          {m.name} <span className="facility-muted">({m.diet})</span>
                        </label>
                      ))}
                    </div>
                  )}
                </>
              )}
              {bookTarget.inventoryItems?.length > 0 && (
                <div className="facility-book-inventory">
                  <span className="facility-meal-label">Optional inventory</span>
                  <p className="facility-modal-hint">Request quantities (subject to availability for your dates).</p>
                  <ul className="facility-book-inventory-list">
                    {bookTarget.inventoryItems.map((it) => (
                      <li key={it.id}>
                        <span className="facility-inv-key">{it.name}</span>
                        <span className="facility-inv-val">in stock {it.quantity_available}</span>
                        <input
                          type="number"
                          min={0}
                          className="facility-inv-qty"
                          placeholder="0"
                          value={bookingInvQty[it.id] ?? ''}
                          onChange={(e) => {
                            const raw = e.target.value;
                            setBookingInvQty((prev) => {
                              const next = { ...prev };
                              if (raw === '') delete next[it.id];
                              else next[it.id] = Math.max(0, parseInt(raw, 10) || 0);
                              return next;
                            });
                          }}
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={closeBookModal}>Cancel</button>
              <button type="button" className="facility-btn-save" onClick={submitBooking} disabled={saving || !!bookingMaintConflictWarning}>{saving ? 'Booking...' : 'Book'}</button>
            </div>
          </div>
        </div>
      )}

      {hostelOccupancyModal && (
        <div className="facility-modal-overlay" onClick={closeHostelOccupancyModal}>
          <div className="facility-modal facility-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>Inmates — room {hostelOccupancyModal.roomno}</h3>
            {hostelOccupancyError && <div className="facility-error">{hostelOccupancyError}</div>}
            {hostelOccupancyLoading && <p className="facility-muted">Loading…</p>}
            {!hostelOccupancyLoading && hostelOccupancyData && (() => {
              const people = mergeHostelInmateUsers(hostelOccupancyData);
              if (people.length === 0) return <p className="facility-muted">No profiles to show.</p>;
              return (
                <ul className="facility-inmates-profile-list">
                  {people.map((u) => (
                    <li key={u.id}>
                      <button type="button" className="facility-link-btn" onClick={() => setUserDetailModal(u)}>
                        {u.name}
                      </button>
                    </li>
                  ))}
                </ul>
              );
            })()}
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={closeHostelOccupancyModal}>Close</button>
            </div>
          </div>
        </div>
      )}

      {stockModal && (
        <div className="facility-modal-overlay" onClick={closeStockModal}>
          <div className="facility-modal facility-modal-booking" onClick={(e) => e.stopPropagation()}>
            <h3>Stock — {stockModal.title}</h3>
            {formError && <div className="facility-error">{formError}</div>}
            <p className="facility-modal-hint">Total units available for this facility. Overlapping bookings cannot exceed these totals.</p>
            <ul className="facility-stock-list">
              {stockItems.map((it) => (
                <li key={it.id} className="facility-stock-row">
                  <span className="facility-inv-key">{it.name}</span>
                  <span className="facility-inv-val">{it.quantity_available}</span>
                  {canEdit && (
                    <button
                      type="button"
                      className="facility-btn-edit"
                      onClick={() => {
                        const v = window.prompt('Quantity available', String(it.quantity_available));
                        if (v === null) return;
                        const n = parseInt(v, 10);
                        if (Number.isNaN(n) || n < 0) return;
                        patchStockQty(it.id, n);
                      }}
                    >
                      Set qty
                    </button>
                  )}
                  {isAdmin && (
                    <button type="button" className="facility-btn-delete" onClick={() => deleteStockItem(it.id)}>
                      Delete
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {isAdmin && (
              <div className="facility-inv-row">
                <input placeholder="Item name" value={stockNewName} onChange={(e) => setStockNewName(e.target.value)} />
                <input type="number" min={0} className="facility-inv-qty" value={stockNewQty} onChange={(e) => setStockNewQty(e.target.value)} />
                <button type="button" className="facility-btn-book" onClick={submitNewStockItem} disabled={saving}>
                  Add item
                </button>
              </div>
            )}
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={closeStockModal}>Close</button>
            </div>
          </div>
        </div>
      )}

      {menuModal && (
        <div className="facility-modal-overlay" onClick={closeMenuModal}>
          <div className="facility-modal facility-modal-booking" onClick={(e) => e.stopPropagation()}>
            <h3>Menu — {menuModal.areaName}</h3>
            {formError && <div className="facility-error">{formError}</div>}
            <ul className="facility-menu-list">
              {menuItems.map((row) => (
                <li key={row.id} className="facility-menu-row">
                  <span><strong>{row.name}</strong> <span className="facility-muted">{row.meal_slot} · {row.diet}</span></span>
                  <span className={row.active ? '' : 'facility-muted'}>{row.active ? 'Active' : 'Inactive'}</span>
                  {canEdit && (
                    <button type="button" className="facility-btn-edit" onClick={() => toggleMenuItemActive(row)}>
                      {row.active ? 'Deactivate' : 'Activate'}
                    </button>
                  )}
                  {isAdmin && (
                    <button type="button" className="facility-btn-delete" onClick={() => deleteMenuItem(row.id)}>
                      Delete
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {isAdmin && (
              <div className="facility-form">
                <label>
                  Slot{' '}
                  <select value={menuNew.meal_slot} onChange={(e) => setMenuNew({ ...menuNew, meal_slot: e.target.value })}>
                    {MEAL_SLOTS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Name <input value={menuNew.name} onChange={(e) => setMenuNew({ ...menuNew, name: e.target.value })} />
                </label>
                <label>
                  Diet{' '}
                  <select value={menuNew.diet} onChange={(e) => setMenuNew({ ...menuNew, diet: e.target.value })}>
                    <option value="either">Either</option>
                    <option value="veg">Veg</option>
                    <option value="non_veg">Non-veg</option>
                  </select>
                </label>
                <button type="button" className="facility-btn-book" onClick={submitNewMenuItem} disabled={saving}>
                  Add menu item
                </button>
              </div>
            )}
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={closeMenuModal}>Close</button>
            </div>
          </div>
        </div>
      )}

      {userDetailModal && (
        <div className="facility-modal-overlay" onClick={() => setUserDetailModal(null)}>
          <div className="facility-modal facility-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>User details</h3>
            <div className="facility-user-detail">
              <p><span className="facility-user-detail-label">Name</span><span>{userDetailModal.name}</span></p>
              <p><span className="facility-user-detail-label">Email</span><span>{userDetailModal.email}</span></p>
              <p><span className="facility-user-detail-label">Phone</span><span>{userDetailModal.phone_number || '—'}</span></p>
              <p><span className="facility-user-detail-label">Role</span><span>{userDetailModal.role}</span></p>
              <p><span className="facility-user-detail-label">User ID</span><span>{userDetailModal.id}</span></p>
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={() => setUserDetailModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {bookEditTarget && (
        <div className="facility-modal-overlay" onClick={closeEditBookingModal}>
          <div className="facility-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Modify booking</h3>
            <p className="facility-modal-hint">Changing times may move an accepted booking back to pending for approval.</p>
            <p className="facility-modal-hint">
              Minimum duration: {bookEditTarget.hostel_room_id ? '1 full day (24 hours) for hostel' : '2 hours for this facility'}.
            </p>
            {formError && <div className="facility-error">{formError}</div>}
            <div className="facility-form">
              <label>Start time <input type="datetime-local" value={editBookingStart} onChange={(e) => setEditBookingStart(e.target.value)} /></label>
              <label>End time <input type="datetime-local" value={editBookingEnd} onChange={(e) => setEditBookingEnd(e.target.value)} /></label>
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={closeEditBookingModal}>Cancel</button>
              <button type="button" className="facility-btn-save" onClick={submitEditBooking} disabled={saving}>{saving ? 'Saving...' : 'Save changes'}</button>
            </div>
          </div>
        </div>
      )}

      {mtIssueViewModal && (
        <div className="facility-modal-overlay" onClick={() => setMtIssueViewModal(null)}>
          <div className="facility-modal facility-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>Issue</h3>
            <div className="facility-user-detail">
              <p><span className="facility-user-detail-label">Summary</span><span>{mtIssueViewModal.title || '—'}</span></p>
              <p className="mt-issue-desc-row">
                <span className="facility-user-detail-label">Description</span>
                <span className="mt-issue-desc-text">{mtIssueViewModal.description?.trim() ? mtIssueViewModal.description : '—'}</span>
              </p>
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={() => setMtIssueViewModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {mtLocationViewModal && (
        <div className="facility-modal-overlay" onClick={() => setMtLocationViewModal(null)}>
          <div className="facility-modal facility-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>Location</h3>
            <div className="facility-user-detail">
              {mtLocationViewModal.label ? (
                <p><span className="facility-user-detail-label">Overview</span><span>{mtLocationViewModal.label}</span></p>
              ) : null}
              {maintenanceLocationDetailRows(mtLocationViewModal.detail).length === 0 ? (
                !mtLocationViewModal.label && <p className="facility-muted">No location details.</p>
              ) : (
                maintenanceLocationDetailRows(mtLocationViewModal.detail).map(([k, v], i) => (
                  <p key={`${k}-${i}`}>
                    <span className="facility-user-detail-label">{k}</span>
                    <span>{v}</span>
                  </p>
                ))
              )}
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-save" onClick={() => setMtLocationViewModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {schedFormOpen && (
        <div className="facility-modal-overlay" onClick={() => setSchedFormOpen(false)}>
          <div className="facility-modal" onClick={(e) => e.stopPropagation()}>
            <h3>New maintenance schedule</h3>
            {maintSchedError && <div className="facility-error">{maintSchedError}</div>}
            <div className="facility-form">
              <label>
                Title <input value={schedTitle} onChange={(e) => setSchedTitle(e.target.value)} placeholder="e.g. HVAC inspection" />
              </label>
              <label>
                Notes <textarea value={schedNotes} onChange={(e) => setSchedNotes(e.target.value)} rows={2} placeholder="Optional details" />
              </label>
              <label>
                Location type{' '}
                <select value={schedResKind} onChange={(e) => setSchedResKind(e.target.value)}>
                  <option value="hostel_room">Hostel room</option>
                  <option value="other_area">Mess, sports, academic, etc.</option>
                </select>
              </label>
              {schedResKind === 'hostel_room' && (
                <label>
                  Room{' '}
                  <select value={schedHostelRoomId} onChange={(e) => setSchedHostelRoomId(e.target.value)}>
                    <option value="">— Select —</option>
                    {hostelRooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.roomno} (id {r.id})
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {schedResKind === 'other_area' && (
                <label>
                  Facility / area{' '}
                  <select value={schedOtherAreaId} onChange={(e) => setSchedOtherAreaId(e.target.value)}>
                    <option value="">— Select —</option>
                    {otherAreas.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} (id {a.id})
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Scheduled start <input type="datetime-local" value={schedStart} onChange={(e) => setSchedStart(e.target.value)} />
              </label>
              <label>
                Scheduled end <input type="datetime-local" value={schedEnd} onChange={(e) => setSchedEnd(e.target.value)} />
              </label>
            </div>
            {maintConflictWarning && <div className="facility-error">{maintConflictWarning}</div>}
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={() => setSchedFormOpen(false)}>
                Cancel
              </button>
              <button type="button" className="facility-btn-save" onClick={submitMaintenanceSchedule} disabled={saving || !!maintConflictWarning}>
                {saving ? 'Saving…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {mtFormOpen && (
        <div className="facility-modal-overlay" onClick={() => setMtFormOpen(false)}>
          <div className="facility-modal" onClick={(e) => e.stopPropagation()}>
            <h3>New maintenance issue</h3>
            {maintenanceError && <div className="facility-error">{maintenanceError}</div>}
            <div className="facility-form">
              <label>
                Issue (short summary){' '}
                <input value={mtTitle} onChange={(e) => setMtTitle(e.target.value)} placeholder="e.g. Leaking tap in washroom" />
              </label>
              <label>
                Description{' '}
                <textarea value={mtDescription} onChange={(e) => setMtDescription(e.target.value)} rows={3} placeholder="What is wrong?" />
              </label>
              <label>
                Location type{' '}
                <select value={mtResourceKind} onChange={(e) => setMtResourceKind(e.target.value)}>
                  <option value="hostel_room">Hostel room</option>
                  <option value="other_area">Mess, sports, academic, etc.</option>
                </select>
              </label>
              {mtResourceKind === 'hostel_room' && (
                <label>
                  Room{' '}
                  <select value={mtHostelRoomId} onChange={(e) => setMtHostelRoomId(e.target.value)}>
                    <option value="">— Select —</option>
                    {hostelRooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.roomno} (id {r.id})
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {mtResourceKind === 'other_area' && (
                <label>
                  Facility / area{' '}
                  <select value={mtOtherAreaId} onChange={(e) => setMtOtherAreaId(e.target.value)}>
                    <option value="">— Select —</option>
                    {otherAreas.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} (id {a.id})
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className="mt-file-label">
                Photos (optional, max 6, 5 MB each){' '}
                <input id="mt-file-input" type="file" accept="image/jpeg,image/png,image/gif,image/webp" multiple />
              </label>
            </div>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={() => setMtFormOpen(false)}>Cancel</button>
              <button type="button" className="facility-btn-save" onClick={submitMaintenanceTicket} disabled={saving}>
                {saving ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="facility-modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="facility-modal facility-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>Delete</h3>
            <p>{deleteConfirm.type === 'booking' ? 'Cancel this booking? This cannot be undone.' : `Delete "${deleteConfirm.name}"? This cannot be undone.`}</p>
            <div className="facility-modal-actions">
              <button type="button" className="facility-btn-cancel" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button type="button" className="facility-btn-delete" onClick={doDelete} disabled={saving}>{saving ? 'Deleting...' : 'Delete'}</button>
            </div>
          </div>
        </div>
      )}

      {notifOpen && (
        <div className="facility-modal-overlay" onClick={() => setNotifOpen(false)}>
          <div className="facility-modal facility-modal-notif" onClick={(e) => e.stopPropagation()}>
            <div className="dashboard-notif-dropdown-head">
              <span>Notifications</span>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <button type="button" className="dashboard-notif-markall" onClick={markAllNotificationsRead} disabled={notifLoading || unreadNotifCount === 0}>
                  Mark all read
                </button>
                <button type="button" className="dashboard-notif-close" onClick={() => setNotifOpen(false)} aria-label="Close">✕</button>
              </div>
            </div>
            {notifLoading && <p className="dashboard-notif-empty">Loading…</p>}
            {!notifLoading && notifications.length === 0 && <p className="dashboard-notif-empty">No notifications yet.</p>}
            <ul className="dashboard-notif-list">
              {notifications.map((n) => (
                <li key={n.id} className={n.read ? 'dashboard-notif-item read' : 'dashboard-notif-item'}>
                  <button
                    type="button"
                    className="dashboard-notif-item-btn"
                    onClick={() => { if (!n.read) markNotificationRead(n.id); }}
                  >
                    <span className="dashboard-notif-title">{n.title}</span>
                    <span className="dashboard-notif-body">{n.body}</span>
                    <span className="dashboard-notif-meta">
                      {n.category} · {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
