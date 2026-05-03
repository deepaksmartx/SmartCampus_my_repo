import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiGet, apiPost, apiPatch, apiDelete, API_BASE } from '../api';
import '../styles/Dashboard.css';
import '../styles/CampusManagement.css';
const CAMPUS_PREFIX = '/campus';

const ProfileIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2.5">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const TABS = [
  { id: 'campuses', label: 'Campuses' },
  { id: 'buildings', label: 'Buildings' },
  { id: 'floors', label: 'Floors' },
  { id: 'facility-types', label: 'Facility Types' },
  { id: 'other-areas', label: 'Other Areas' },
  { id: 'hostel-rooms', label: 'Hostel Rooms' },
];

const FACILITY_TYPE_OPTIONS = ['mens_hostel', 'ladies_hostel', 'dining', 'sports', 'academic_spaces'];
const ROOM_TYPE_OPTIONS = ['Single', 'Double', 'Suite'];

function CampusManagement() {
  const navigate = useNavigate();
  const profileRef = useRef(null);
  const [profile, setProfile] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('campuses');
  const [lists, setLists] = useState({
    campuses: [], buildings: [], floors: [], facilityTypes: [], otherAreas: [], hostelRooms: [],
  });
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null); // { type: 'add'|'edit', entity, data }
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const isAdmin = profile?.role === 'Admin';
  const canEdit = profile?.role === 'Admin' || profile?.role === 'Facility Manager';

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

  const loadList = async (entity) => {
    setListLoading(true);
    setError('');
    try {
      const path = {
        campuses: `${CAMPUS_PREFIX}/campuses`,
        buildings: `${CAMPUS_PREFIX}/buildings`,
        floors: `${CAMPUS_PREFIX}/floors`,
        'facility-types': `${CAMPUS_PREFIX}/facility-types`,
        'other-areas': `${CAMPUS_PREFIX}/other-areas`,
        'hostel-rooms': `${CAMPUS_PREFIX}/hostel-rooms`,
      }[entity];
      const keyMap = { campuses: 'campuses', buildings: 'buildings', floors: 'floors', 'facility-types': 'facilityTypes', 'other-areas': 'otherAreas', 'hostel-rooms': 'hostelRooms' };
      const data = await apiGet(path);
      setLists((prev) => ({ ...prev, [keyMap[entity]]: Array.isArray(data) ? data : [] }));
    } catch (e) {
      setError(e.message || 'Failed to load');
      const keyMap = { campuses: 'campuses', buildings: 'buildings', floors: 'floors', 'facility-types': 'facilityTypes', 'other-areas': 'otherAreas', 'hostel-rooms': 'hostelRooms' };
      setLists((prev) => ({ ...prev, [keyMap[entity]]: [] }));
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    if (!profile) return;
    const key = activeTab === 'facility-types' ? 'facilityTypes' : activeTab === 'other-areas' ? 'otherAreas' : activeTab === 'hostel-rooms' ? 'hostelRooms' : activeTab;
    loadList(activeTab);
  }, [profile, activeTab]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/');
  };

  const openAdd = () => {
    const empty = {
      campuses: { name: '', location: '' },
      buildings: { name: '', campus_id: lists.campuses[0]?.id || 0 },
      floors: { building_id: lists.buildings[0]?.id || 0, floor_no: 0 },
      'facility-types': { name: 'mens_hostel' },
      'other-areas': { name: '', building_id: lists.buildings[0]?.id || 0, floor_id: lists.floors[0]?.id || 0, capacity: 0, facility_type_id: lists.facilityTypes[0]?.id || 0, active: true, requires_approval: false },
      'hostel-rooms': { roomno: '', room_type: 'Single', facility_type_id: lists.facilityTypes[0]?.id || 0, inmate_profiles: [], room_capacity: 1 },
    };
    setModal({ type: 'add', entity: activeTab, data: empty[activeTab] || {} });
    setFormError('');
  };

  const openEdit = (row) => {
    setModal({ type: 'edit', entity: activeTab, data: { ...row }, id: row.id });
    setFormError('');
  };

  const closeModal = () => setModal(null);

  const saveModal = async () => {
    if (!modal) return;
    setSaving(true);
    setFormError('');
    try {
      const pathMap = {
        campuses: (id) => `${CAMPUS_PREFIX}/campuses${id != null ? `/${id}` : ''}`,
        buildings: (id) => `${CAMPUS_PREFIX}/buildings${id != null ? `/${id}` : ''}`,
        floors: (id) => `${CAMPUS_PREFIX}/floors${id != null ? `/${id}` : ''}`,
        'facility-types': (id) => `${CAMPUS_PREFIX}/facility-types${id != null ? `/${id}` : ''}`,
        'other-areas': (id) => `${CAMPUS_PREFIX}/other-areas${id != null ? `/${id}` : ''}`,
        'hostel-rooms': (id) => `${CAMPUS_PREFIX}/hostel-rooms${id != null ? `/${id}` : ''}`,
      };
      const path = pathMap[modal.entity](modal.id);
      if (modal.type === 'add') {
        await apiPost(path, modal.data);
      } else {
        const { id, ...body } = modal.data;
        await apiPatch(path, body);
      }
      closeModal();
      loadList(activeTab);
    } catch (e) {
      setFormError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!deleteConfirm) return;
    setSaving(true);
    setFormError('');
    try {
      const pathMap = {
        campuses: (id) => `${CAMPUS_PREFIX}/campuses/${id}`,
        buildings: (id) => `${CAMPUS_PREFIX}/buildings/${id}`,
        floors: (id) => `${CAMPUS_PREFIX}/floors/${id}`,
        'facility-types': (id) => `${CAMPUS_PREFIX}/facility-types/${id}`,
        'other-areas': (id) => `${CAMPUS_PREFIX}/other-areas/${id}`,
        'hostel-rooms': (id) => `${CAMPUS_PREFIX}/hostel-rooms/${id}`,
      };
      await apiDelete(pathMap[deleteConfirm.entity](deleteConfirm.id));
      setDeleteConfirm(null);
      loadList(activeTab);
    } catch (e) {
      setFormError(e.message || 'Delete failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="campus-page">
        <div className="campus-loading">Loading...</div>
      </div>
    );
  }

  const listKey = activeTab === 'facility-types' ? 'facilityTypes' : activeTab === 'other-areas' ? 'otherAreas' : activeTab === 'hostel-rooms' ? 'hostelRooms' : activeTab;
  const rows = lists[listKey] || [];

  return (
    <div className="campus-page">
      <header className="dashboard-header">
        <span className="dashboard-header-title">SmartCampus</span>
        <div className="dashboard-header-actions">
          <Link to="/dashboard" className="dashboard-header-btn" style={{ textDecoration: 'none', color: 'white' }}>Dashboard</Link>
          <div className="dashboard-profile-wrap" ref={profileRef}>
            <button type="button" className="dashboard-profile-icon-btn" onClick={() => setProfileOpen(!profileOpen)} aria-label="Profile">
              <ProfileIcon />
            </button>
            {profileOpen && profile && (
              <div className="dashboard-profile-dropdown">
                <div className="dashboard-profile-dropdown-row"><span className="label">Name</span><span className="value">{profile.name}</span></div>
                <div className="dashboard-profile-dropdown-row"><span className="label">Email</span><span className="value">{profile.email}</span></div>
                <div className="dashboard-profile-dropdown-row"><span className="label">Role</span><span className="value">{profile.role}</span></div>
              </div>
            )}
          </div>
          <button type="button" className="dashboard-header-btn dashboard-header-logout" onClick={handleLogout}>Logout</button>
        </div>
      </header>

      <div className="campus-content">
        <div className="campus-tabs">
          {TABS.map((t) => (
            <button key={t.id} type="button" className={`campus-tab ${activeTab === t.id ? 'active' : ''}`} onClick={() => setActiveTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {error && <div className="campus-error">{error}</div>}
        {formError && <div className="campus-error">{formError}</div>}

        <div className="campus-toolbar">
          {isAdmin && (
            <button type="button" className="campus-btn-add" onClick={openAdd}>+ Add {TABS.find((t) => t.id === activeTab)?.label?.slice(0, -1) || 'Item'}</button>
          )}
        </div>

        {listLoading ? (
          <div className="campus-loading-table">Loading...</div>
        ) : (
          <div className="campus-table-wrap">
            {activeTab === 'campuses' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Name</th><th>Location</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.name}</td><td>{r.location ?? '—'}</td>
                      {canEdit && <td><button type="button" className="campus-btn-edit" onClick={() => openEdit(r)}>Edit</button></td>}
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: r.name })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {activeTab === 'buildings' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Name</th><th>Campus ID</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.name}</td><td>{r.campus_id}</td>
                      {canEdit && <td><button type="button" className="campus-btn-edit" onClick={() => openEdit(r)}>Edit</button></td>}
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: r.name })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {activeTab === 'floors' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Building ID</th><th>Floor No</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.building_id}</td><td>{r.floor_no}</td>
                      {canEdit && <td><button type="button" className="campus-btn-edit" onClick={() => openEdit(r)}>Edit</button></td>}
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: `Floor ${r.floor_no}` })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {activeTab === 'facility-types' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Name</th>{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.name}</td>
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: r.name })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {activeTab === 'other-areas' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Name</th><th>Building</th><th>Floor</th><th>Capacity</th><th>Active</th><th>Requires Approval</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.name}</td><td>{r.building_id}</td><td>{r.floor_id}</td><td>{r.capacity ?? '—'}</td><td>{r.active ? 'Yes' : 'No'}</td><td>{r.requires_approval ? 'Yes' : 'No'}</td>
                      {canEdit && <td><button type="button" className="campus-btn-edit" onClick={() => openEdit(r)}>Edit</button></td>}
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: r.name })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {activeTab === 'hostel-rooms' && (
              <table className="campus-table">
                <thead><tr><th>ID</th><th>Room No</th><th>Type</th><th>Facility Type ID</th><th>Capacity</th><th>Inmates</th>{canEdit && <th>Edit</th>}{isAdmin && <th>Delete</th>}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}><td>{r.id}</td><td>{r.roomno}</td><td>{r.room_type}</td><td>{r.facility_type_id}</td><td>{r.room_capacity}</td><td>{(r.inmate_profiles || []).length}</td>
                      {canEdit && <td><button type="button" className="campus-btn-edit" onClick={() => openEdit(r)}>Edit</button></td>}
                      {isAdmin && <td><button type="button" className="campus-btn-delete" onClick={() => setDeleteConfirm({ entity: activeTab, id: r.id, name: r.roomno })}>Delete</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {rows.length === 0 && !listLoading && <p className="campus-empty">No items yet.</p>}
      </div>

      {/* Add/Edit Modal */}
      {modal && (
        <div className="campus-modal-overlay" onClick={closeModal}>
          <div className="campus-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{modal.type === 'add' ? 'Add' : 'Edit'} {TABS.find((t) => t.id === modal.entity)?.label?.slice(0, -1) || 'Item'}</h3>
            {modal.entity === 'campuses' && (
              <div className="campus-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Location <input value={modal.data.location || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, location: e.target.value } })} /></label>
              </div>
            )}
            {modal.entity === 'buildings' && (
              <div className="campus-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Campus <select value={modal.data.campus_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, campus_id: +e.target.value } })}>
                  {lists.campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select></label>
              </div>
            )}
            {modal.entity === 'floors' && (
              <div className="campus-form">
                <label>Building <select value={modal.data.building_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, building_id: +e.target.value } })}>
                  {lists.buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select></label>
                <label>Floor No <input type="number" value={modal.data.floor_no ?? ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, floor_no: +e.target.value } })} /></label>
              </div>
            )}
            {modal.entity === 'facility-types' && (
              <div className="campus-form">
                <label>Name <select value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })}>
                  {FACILITY_TYPE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
                </select></label>
              </div>
            )}
            {modal.entity === 'other-areas' && (
              <div className="campus-form">
                <label>Name <input value={modal.data.name || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, name: e.target.value } })} /></label>
                <label>Building <select value={modal.data.building_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, building_id: +e.target.value } })}>
                  {lists.buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select></label>
                <label>Floor <select value={modal.data.floor_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, floor_id: +e.target.value } })}>
                  {lists.floors.map((f) => <option key={f.id} value={f.id}>{f.floor_no}</option>)}
                </select></label>
                <label>Capacity <input type="number" value={modal.data.capacity ?? ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, capacity: e.target.value ? +e.target.value : null } })} /></label>
                <label>Facility Type <select value={modal.data.facility_type_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, facility_type_id: +e.target.value } })}>
                  {lists.facilityTypes.map((ft) => <option key={ft.id} value={ft.id}>{ft.name}</option>)}
                </select></label>
                <label><input type="checkbox" checked={!!modal.data.active} onChange={(e) => setModal({ ...modal, data: { ...modal.data, active: e.target.checked } })} /> Active</label>
                <label><input type="checkbox" checked={!!modal.data.requires_approval} onChange={(e) => setModal({ ...modal, data: { ...modal.data, requires_approval: e.target.checked } })} /> Requires Approval</label>
              </div>
            )}
            {modal.entity === 'hostel-rooms' && (
              <div className="campus-form">
                <label>Room No <input value={modal.data.roomno || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, roomno: e.target.value } })} /></label>
                <label>Room Type <select value={modal.data.room_type || 'Single'} onChange={(e) => setModal({ ...modal, data: { ...modal.data, room_type: e.target.value } })}>
                  {ROOM_TYPE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
                </select></label>
                <label>Facility Type <select value={modal.data.facility_type_id || ''} onChange={(e) => setModal({ ...modal, data: { ...modal.data, facility_type_id: +e.target.value } })}>
                  {lists.facilityTypes.map((ft) => <option key={ft.id} value={ft.id}>{ft.name}</option>)}
                </select></label>
                <label>Room Capacity <input type="number" value={modal.data.room_capacity ?? 1} onChange={(e) => setModal({ ...modal, data: { ...modal.data, room_capacity: +e.target.value || 1 } })} /></label>
              </div>
            )}
            <div className="campus-modal-actions">
              <button type="button" className="campus-btn-cancel" onClick={closeModal}>Cancel</button>
              <button type="button" className="campus-btn-save" onClick={saveModal} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteConfirm && (
        <div className="campus-modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="campus-modal campus-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h3>Delete</h3>
            <p>Delete &quot;{deleteConfirm.name}&quot;? This cannot be undone.</p>
            <div className="campus-modal-actions">
              <button type="button" className="campus-btn-cancel" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button type="button" className="campus-btn-delete" onClick={doDelete} disabled={saving}>{saving ? 'Deleting...' : 'Delete'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CampusManagement;
