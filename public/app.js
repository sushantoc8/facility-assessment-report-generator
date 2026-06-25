const lookupForm = document.getElementById('lookupForm');
const lookupButton = document.getElementById('lookupButton');
const lookupStatus = document.getElementById('lookupStatus');
const ccnInput = document.getElementById('ccnInput');
const downloadButton = document.getElementById('downloadButton');
const reportTableBody = document.querySelector('#reportTable tbody');
const emptyRowsTemplate = document.getElementById('emptyReportRows');
const officialName = document.getElementById('officialName');
const locationEl = document.getElementById('location');
const censusCapacity = document.getElementById('censusCapacity');
const ratings = document.getElementById('ratings');
const careCompareLink = document.getElementById('careCompareLink');
const previewState = document.getElementById('previewState');

const manualInputs = {
  facilityNameOverride: document.getElementById('facilityNameOverride'),
  emr: document.getElementById('emr'),
  currentCensus: document.getElementById('currentCensus'),
  patientType: document.getElementById('patientType'),
  previousCoverage: document.getElementById('previousCoverage'),
  previousProviderPerformance: document.getElementById('previousProviderPerformance'),
  medicalCoverage: document.getElementById('medicalCoverage'),
};

let currentSnapshot = null;

const BASE_ROW_DEFS = [
  ['Name of Facility', 'facilityName'],
  ['Location', 'location'],
  ['EMR', 'emr'],
  ['Census Capacity', 'censusCapacity'],
  ['Current Census', 'currentCensus'],
  ['Type of Patient', 'patientType'],
  ['Previous Coverage from Medelite', 'previousCoverage'],
  ['Previous Provider Performance from Medelite', 'previousProviderPerformance'],
  ['Medical Coverage', 'medicalCoverage'],
  ['Overall Star Rating', 'overallRating'],
  ['Health Inspection', 'healthInspection'],
  ['Staffing', 'staffing'],
  ['Quality of Resident Care', 'qualityResidentCare'],
];

function setStatus(message, type = '') {
  lookupStatus.textContent = message;
  lookupStatus.className = `status ${type}`.trim();
}

function clean(value) {
  if (value === null || value === undefined || String(value).trim() === '') return '—';
  return String(value).trim();
}

function getManualPayload() {
  return Object.fromEntries(
    Object.entries(manualInputs).map(([key, element]) => [key, element.value.trim()])
  );
}

function buildPayload() {
  if (!currentSnapshot) return null;
  return {
    ...currentSnapshot,
    manual: getManualPayload(),
  };
}

function resetReportTable() {
  reportTableBody.innerHTML = emptyRowsTemplate.innerHTML;
  if (previewState) previewState.textContent = '—';
}

function renderCmsPreview(snapshot) {
  const provider = snapshot?.provider || {};
  const ratingValues = provider.ratings || {};
  officialName.textContent = clean(provider.officialName);
  locationEl.textContent = clean(provider.location);
  censusCapacity.textContent = clean(provider.censusCapacity);
  ratings.textContent = `${clean(ratingValues.overall)} / ${clean(ratingValues.healthInspection)} / ${clean(ratingValues.staffing)} / ${clean(ratingValues.qualityResidentCare)}`;

  if (snapshot?.careCompareUrl) {
    careCompareLink.href = snapshot.careCompareUrl;
    careCompareLink.classList.remove('hidden');
  } else {
    careCompareLink.removeAttribute('href');
    careCompareLink.classList.add('hidden');
  }
}

function buildReportRows(payload) {
  const provider = payload?.provider || {};
  const manual = payload?.manual || {};
  const ratingValues = provider.ratings || {};
  const baseValues = {
    facilityName: manual.facilityNameOverride || provider.officialName,
    location: provider.location,
    emr: manual.emr,
    censusCapacity: provider.censusCapacity,
    currentCensus: manual.currentCensus,
    patientType: manual.patientType,
    previousCoverage: manual.previousCoverage,
    previousProviderPerformance: manual.previousProviderPerformance,
    medicalCoverage: manual.medicalCoverage,
    overallRating: ratingValues.overall,
    healthInspection: ratingValues.healthInspection,
    staffing: ratingValues.staffing,
    qualityResidentCare: ratingValues.qualityResidentCare,
  };

  const rows = BASE_ROW_DEFS.map(([label, key]) => ({ label, value: clean(baseValues[key]), kind: 'base' }));
  for (const metric of payload?.metrics || []) {
    rows.push({ label: clean(metric.label), value: clean(metric.value), kind: 'metric' });
  }
  return rows;
}

function renderReportPreview() {
  const payload = buildPayload();
  if (!payload) {
    resetReportTable();
    return;
  }
  if (previewState) previewState.textContent = clean(payload.state || payload.provider?.state);
  reportTableBody.innerHTML = '';
  for (const row of buildReportRows(payload)) {
    const tr = document.createElement('tr');
    if (row.kind === 'metric') tr.classList.add('metric');
    const th = document.createElement('th');
    const td = document.createElement('td');
    th.textContent = row.label;
    td.textContent = row.value;
    tr.append(th, td);
    reportTableBody.appendChild(tr);
  }
}

async function lookupFacility(ccn) {
  lookupButton.disabled = true;
  downloadButton.disabled = true;
  setStatus('Fetching CMS Provider Data Catalog records...');

  try {
    const response = await fetch(`/api/facility/${encodeURIComponent(ccn)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Lookup failed.');
    }
    currentSnapshot = payload.data;
    renderCmsPreview(currentSnapshot);
    renderReportPreview();
    downloadButton.disabled = false;
    setStatus(`Loaded ${currentSnapshot.provider.officialName || 'facility'} from CMS.`, 'success');
  } catch (error) {
    currentSnapshot = null;
    renderCmsPreview(null);
    resetReportTable();
    setStatus(error.message, 'error');
  } finally {
    lookupButton.disabled = false;
  }
}

async function downloadPdf() {
  const payload = buildPayload();
  if (!payload) return;

  downloadButton.disabled = true;
  const originalText = downloadButton.textContent;
  downloadButton.textContent = 'Building PDF...';

  try {
    const response = await fetch('/api/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      let message = 'Unable to generate PDF.';
      try {
        const error = await response.json();
        message = error.error || message;
      } catch (_) {}
      throw new Error(message);
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const fileName = match ? match[1] : 'facility_assessment_snapshot.pdf';
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    downloadButton.disabled = false;
    downloadButton.textContent = originalText;
  }
}

lookupForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const ccn = ccnInput.value.replace(/\D/g, '');
  ccnInput.value = ccn;
  if (!/^\d{6}$/.test(ccn)) {
    setStatus('Please enter a valid 6-digit CCN.', 'error');
    return;
  }
  lookupFacility(ccn);
});


downloadButton.addEventListener('click', downloadPdf);

for (const input of Object.values(manualInputs)) {
  input.addEventListener('input', renderReportPreview);
  input.addEventListener('change', renderReportPreview);
}

resetReportTable();
