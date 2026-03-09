<script setup>
import { ref, computed } from "vue";
import { useRoute } from "vue-router";
import axios from "axios";
import { addPopup, getCurrentApiUrl, getDataOrPopupError, parseDataOrPopupError, postDataOrPopupError } from "@/assets/utils";

const route = useRoute();
const id = route.params.id;

const entry = ref(null);
const schemas = ref([]);
const tables = ref([]);
const columns = ref([]);
const schema = ref("");
const table = ref("");
const sql = ref("");
const result = ref({ columns: [], rows: [] });
const selected = ref(new Set());
const pkCols = ref([]);
const editOpen = ref(false);
const editRowIndex = ref(-1);
const editValues = ref({});
const status = ref("");
const cellOpen = ref(false);
const cellValue = ref("");
const grants = ref([]);
const grantUser = ref("");
const rowHeight = ref(56);

const privilegeTokens = computed(() => {
  const tokens = new Set();
  for (const g of grants.value || []) {
    const text = String(g).toUpperCase();
    if (text.includes("ALL PRIVILEGES") || text.includes("ALL")) {
      tokens.add("ALL");
    }
    if (text.includes("SELECT")) tokens.add("SELECT");
    if (text.includes("INSERT")) tokens.add("INSERT");
    if (text.includes("UPDATE")) tokens.add("UPDATE");
    if (text.includes("DELETE")) tokens.add("DELETE");
    if (text.includes("CREATE")) tokens.add("CREATE");
    if (text.includes("DROP")) tokens.add("DROP");
    if (text.includes("ALTER")) tokens.add("ALTER");
    if (text.includes("GRANT")) tokens.add("GRANT");
  }
  return tokens;
});

const canRead = computed(() => privilegeTokens.value.has("ALL") || privilegeTokens.value.has("SELECT"));
const canWrite = computed(() => privilegeTokens.value.has("ALL") || privilegeTokens.value.has("INSERT") || privilegeTokens.value.has("UPDATE") || privilegeTokens.value.has("DELETE"));
const canEdit = computed(() => privilegeTokens.value.has("ALL") || privilegeTokens.value.has("UPDATE"));
const canDelete = computed(() => privilegeTokens.value.has("ALL") || privilegeTokens.value.has("DELETE"));
const privilegeSummary = computed(() => {
  const list = [];
  if (canRead.value) list.push("Read (SELECT)");
  if (privilegeTokens.value.has("INSERT") || privilegeTokens.value.has("ALL")) list.push("Insert");
  if (privilegeTokens.value.has("UPDATE") || privilegeTokens.value.has("ALL")) list.push("Update");
  if (privilegeTokens.value.has("DELETE") || privilegeTokens.value.has("ALL")) list.push("Delete");
  if (privilegeTokens.value.has("CREATE") || privilegeTokens.value.has("ALL")) list.push("Create");
  if (privilegeTokens.value.has("ALTER") || privilegeTokens.value.has("ALL")) list.push("Alter");
  if (privilegeTokens.value.has("DROP") || privilegeTokens.value.has("ALL")) list.push("Drop");
  if (privilegeTokens.value.has("GRANT") || privilegeTokens.value.has("ALL")) list.push("Grant");
  if (!list.length) list.push("Unknown");
  if (canRead.value && !canWrite.value) list.push("Read-only");
  return list;
});

async function loadEntry() {
  const list = await getDataOrPopupError("/dbms");
  entry.value = list.find(x => x.dbms_id === id);
}

async function loadSchemas() {
  schemas.value = await getDataOrPopupError(`/dbms/${id}/schemas`);
}

async function loadTables(s) {
  schema.value = s || "";
  tables.value = await getDataOrPopupError(`/dbms/${id}/tables?schema=${encodeURIComponent(schema.value||"")}`);
}

async function loadColumns() {
  if (!table.value) return;
  columns.value = await getDataOrPopupError(`/dbms/${id}/columns?schema=${encodeURIComponent(schema.value||"")}&table=${encodeURIComponent(table.value)}`);
  pkCols.value = await getDataOrPopupError(`/dbms/${id}/primary_key?schema=${encodeURIComponent(schema.value||"")}&table=${encodeURIComponent(table.value)}`);
}

function pickTable(t) {
  table.value = t;
  sql.value = `SELECT * FROM ${schema.value ? `${schema.value}.` : ``}${table.value} LIMIT 100`;
  result.value = { columns: [], rows: [] };
  selected.value = new Set();
  loadColumns();
}

async function run() {
  try {
    const data = await postDataOrPopupError(`/dbms/${id}/query`, { sql: sql.value, params: {}, max_rows: 200, schema: schema.value || null });
    if (data?.columns) {
      result.value = data;
      selected.value = new Set();
      status.value = `Rows fetched: ${data.rowcount ?? data.rows.length}`;
      addPopup("green", "Success", status.value);
    } else {
      status.value = `Rows affected: ${data.rowcount}`;
      addPopup("green", "Success", status.value);
    }
  } catch (err) {
    addPopup("red", "Query failed", String(err));
  }
}

function toggleRow(idx) {
  if (selected.value.has(idx)) selected.value.delete(idx);
  else selected.value.add(idx);
}

function keyForRow(row) {
  const key = {};
  if (pkCols.value && pkCols.value.length) {
    for (const c of pkCols.value) key[c] = row[c];
  } else {
    for (const c of Object.keys(row)) key[c] = row[c];
  }
  return key;
}

async function deleteSelected() {
  if (!table.value) return;
  const keys = Array.from(selected.value).map(i => keyForRow(result.value.rows[i]));
  try {
    const resp = await axios.post(`${getCurrentApiUrl()}/dbms/${id}/delete`, { schema: schema.value || null, table: table.value, keys });
    const data = parseDataOrPopupError(resp);
    addPopup("green", "Deleted", `Rows deleted: ${data.deleted}`);
    await run();
  } catch (err) {
    addPopup("red", "Delete failed", String(err));
  }
}

async function deleteRow(i) {
  const keys = [keyForRow(result.value.rows[i])];
  try {
    const resp = await axios.post(`${getCurrentApiUrl()}/dbms/${id}/delete`, { schema: schema.value || null, table: table.value, keys });
    const data = parseDataOrPopupError(resp);
    addPopup("green", "Deleted", `Rows deleted: ${data.deleted}`);
    await run();
  } catch (err) {
    addPopup("red", "Delete failed", String(err));
  }
}

function openEditRow(i) {
  editRowIndex.value = i;
  editValues.value = { ...result.value.rows[i] };
  editOpen.value = true;
}

function closeEdit() {
  editOpen.value = false;
  editRowIndex.value = -1;
  editValues.value = {};
}

function openCell(value) {
  cellValue.value = value == null ? "" : String(value);
  cellOpen.value = true;
}

function closeCell() {
  cellOpen.value = false;
  cellValue.value = "";
}

async function saveEdit() {
  if (editRowIndex.value < 0) return;
  const key = keyForRow(result.value.rows[editRowIndex.value]);
  try {
    const resp = await axios.post(`${getCurrentApiUrl()}/dbms/${id}/update`, { schema: schema.value || null, table: table.value, key, values: editValues.value });
    const data = parseDataOrPopupError(resp);
    addPopup("green", "Updated", `Rows updated: ${data.updated}`);
    await run();
    closeEdit();
  } catch (err) {
    addPopup("red", "Update failed", String(err));
  }
}

async function init() {
  await loadEntry();
  await loadSchemas();
  await loadGrants();
}
init();

async function loadGrants() {
  try {
    const data = await getDataOrPopupError(`/dbms/${id}/grants`);
    grantUser.value = data.user || "";
    grants.value = data.grants || [];
  } catch {}
}
</script>

<template>
  <div class="dbms-detail" v-if="entry">
    <div class="header">
      <div class="title">{{ entry.name }}</div>
      <div class="meta">{{ entry.db_type.toUpperCase() }} • {{ entry.host }}:{{ entry.port }}</div>
    </div>
    <div class="layout">
      <aside class="sidebar shadow-box">
        <div class="section">
          <div class="section-title">Schemas</div>
          <div class="chips">
            <button v-for="s in schemas" :class="{active: s===schema}" @click="loadTables(s)">{{ s }}</button>
          </div>
        </div>
        <div class="section" v-if="tables.length">
          <div class="section-title">Tables</div>
          <div class="list">
            <button v-for="t in tables" :class="{active: t===table}" @click="pickTable(t)">{{ t }}</button>
          </div>
        </div>
      </aside>
      <main class="content shadow-box">
        <div class="grants">
          <div class="grants-header">
            <div>Privileges</div>
            <button @click="loadGrants">Load</button>
          </div>
          <div class="grant-user" v-if="grantUser">User: {{ grantUser }}</div>
          <div class="grant-summary">
            <span v-for="s in privilegeSummary" class="pill">{{ s }}</span>
          </div>
          <div class="grant-list">
            <label v-for="g in grants" class="grant-item">
              <input type="checkbox" checked disabled>
              <span>{{ g }}</span>
            </label>
          </div>
        </div>
        <div class="sql">
          <textarea v-model="sql" rows="6" placeholder="Write SQL here"></textarea>
          <div class="toolbar">
            <button @click="run">Run</button>
            <button v-if="canDelete" class="danger" :disabled="!selected.size" @click="deleteSelected">Delete selected</button>
            <div class="status" v-if="status">{{ status }}</div>
            <div class="row-size">
              <span>Row height</span>
              <input type="range" min="40" max="160" v-model="rowHeight">
              <span>{{ rowHeight }}px</span>
            </div>
          </div>
        </div>
        <div class="grid" v-if="result.columns.length" :style="{ '--row-height': rowHeight + 'px' }">
          <table>
            <tr>
              <th><input type="checkbox" @change="(e)=>{ if(e.target.checked){ selected = new Set(result.rows.map((_,i)=>i)) } else { selected = new Set() } }"></th>
              <th v-for="c in result.columns">{{ c }}</th>
              <th v-if="canEdit || canDelete">Actions</th>
            </tr>
            <tr v-for="(r,i) in result.rows">
              <td><input type="checkbox" :checked="selected.has(i)" @change="toggleRow(i)"></td>
              <td v-for="c in result.columns">
                <button class="cell" @click="openCell(r[c])" :title="String(r[c] ?? '')">{{ r[c] }}</button>
              </td>
              <td class="actions" v-if="canEdit || canDelete">
                <button v-if="canEdit" @click="openEditRow(i)">Edit</button>
                <button v-if="canDelete" class="danger" @click="deleteRow(i)">Delete</button>
              </td>
            </tr>
          </table>
        </div>
      </main>
    </div>
    <div class="modal" v-if="editOpen">
      <div class="modal-card">
        <div class="modal-title">Edit Row</div>
        <div class="modal-grid">
          <label v-for="c in result.columns">
            <span>{{ c }}</span>
            <input type="text" v-model="editValues[c]">
          </label>
        </div>
        <div class="modal-actions">
          <button @click="saveEdit">Save</button>
          <button class="danger" @click="closeEdit">Cancel</button>
        </div>
      </div>
    </div>
    <div class="modal" v-if="cellOpen">
      <div class="modal-card">
        <div class="modal-title">Cell Detail</div>
        <pre class="cell-detail">{{ cellValue }}</pre>
        <div class="modal-actions">
          <button @click="closeCell">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dbms-detail { display: flex; flex-direction: column; gap: 16px; }
.header { display: flex; flex-direction: column; gap: 4px; }
.title { font-size: 18px; font-weight: 700; }
.meta { opacity: 0.8; }
.layout { display: grid; grid-template-columns: minmax(220px, 320px) 1fr; gap: 16px; resize: horizontal; overflow: auto; align-items: stretch; }
.shadow-box { background-color: var(--background-color-2); border-radius: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); }
.sidebar { padding: 16px; }
.section { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.section-title { font-weight: 600; }
.chips, .list { display: flex; flex-wrap: wrap; gap: 8px; }
.chips button, .list button { border: none; height: 28px; padding: 0 10px; border-radius: 999px; background-color: var(--background-color-3); color: var(--font-color-primary); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }
.chips button.active, .list button.active { outline: 2px solid rgba(255,255,255,0.15); }
.content { padding: 24px; display: flex; flex-direction: column; gap: 14px; color: #e6eef5; min-height: 70vh; }
.grants { background: var(--background-color-3); border-radius: 12px; padding: 10px; }
.grants-header { display: flex; justify-content: space-between; align-items: center; }
.grants-header button { height: 30px; border: none; border-radius: 8px; background-color: var(--background-color-2); color: #e6eef5; }
.grant-user { font-size: 12px; opacity: 0.85; margin-top: 6px; }
.grant-summary { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.pill { background: rgba(255,255,255,0.08); color: #e6eef5; border-radius: 999px; padding: 2px 8px; font-size: 11px; }
.grant-list { margin: 6px 0 0; max-height: 160px; overflow: auto; display: grid; gap: 6px; }
.grant-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #e6eef5; }
.grant-item input { accent-color: #5dbf6a; }
.sql textarea { width: 100%; border: none; border-radius: 10px; background-color: var(--background-color-3); color: var(--font-color-primary); padding: 10px; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); resize: vertical; min-height: 120px; }
.toolbar { display: flex; gap: 8px; }
.toolbar button { height: 36px; border: none; border-radius: 10px; background-color: var(--background-color-3); color: var(--font-color-primary); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }
.toolbar button.danger { background-color: #8b3a3a; }
.status { margin-left: auto; color: #d9e6f2; font-size: 12px; opacity: 0.9; }
.grid { width: 100%; overflow-x: auto; }
.grid table { width: max-content; min-width: 100%; }
.grid th { color: #dfe9f0; }
.grid td { color: #e6eef5; }
.actions { display: flex; gap: 6px; }
.grid th, .grid td { padding: 14px 8px; text-align: left; vertical-align: top; }
.grid td { height: var(--row-height); }
.grid tr { height: var(--row-height); }
.row-size { display: flex; align-items: center; gap: 6px; color: #dfe9f0; font-size: 12px; margin-left: auto; }
.row-size input { width: 120px; }
.grid tr:nth-child(even) td { background-color: rgba(255,255,255,0.03); }
.danger { background-color: #8b3a3a; color: #fff; border: none; border-radius: 8px; height: 28px; padding: 0 10px; }
.cell {
  max-width: 260px;
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: transparent;
  border: none;
  color: #e6eef5;
  text-align: left;
  cursor: pointer;
}
.cell-detail {
  white-space: pre-wrap;
  word-break: break-word;
  color: #e6eef5;
  max-height: 60vh;
  overflow: auto;
}
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; padding: 16px; }
.modal-card { width: min(760px, 100%); background: var(--background-color-2); border-radius: 14px; padding: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
.modal-title { font-weight: 700; margin-bottom: 10px; color: #e6eef5; }
.modal-grid { display: grid; grid-template-columns: repeat(2, minmax(140px, 1fr)); gap: 10px; max-height: 50vh; overflow: auto; }
.modal-grid label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #cfd9e3; }
.modal-grid input { height: 34px; border: none; border-radius: 8px; background-color: var(--background-color-3); color: #e6eef5; padding: 0 8px; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
.modal-actions button { height: 36px; border: none; border-radius: 10px; background-color: var(--background-color-3); color: var(--font-color-primary); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }
@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { order: 2; }
  .content { order: 1; }
}
@media (max-width: 560px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .grid table { display: block; }
  .modal-grid { grid-template-columns: 1fr; }
  .cell { max-width: 140px; }
  .row-size { width: 100%; margin-left: 0; }
}
</style>
