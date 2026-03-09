<script setup>
import { ref } from "vue";
import { addPopup, getCurrentApiUrl, getDataOrPopupError, postDataOrPopupError, parseDataOrPopupError } from "@/assets/utils";
import axios from "axios";

const entries = ref([]);
const loading = ref(false);
const activeId = ref(null);
const schemas = ref([]);
const tables = ref([]);
const sql = ref("SELECT 1");
const result = ref({ columns: [], rows: [] });
const activeSchema = ref("");

const form = ref({
  dbms_id: null,
  name: "",
  db_type: "mysql",
  host: "",
  port: 3306,
  username: "",
  password: "",
  database: "",
  options: {}
});

async function fetchList() {
  loading.value = true;
  try {
    entries.value = await getDataOrPopupError("/dbms");
  } finally {
    loading.value = false;
  }
}

async function onSubmit(e) {
  e.preventDefault();
  try {
    const saved = await postDataOrPopupError("/dbms", form.value);
    addPopup("green", "Saved", `DBMS ${saved.name} saved`);
    await fetchList();
    form.value = {
      dbms_id: null,
      name: "",
      db_type: "mysql",
      host: "",
      port: 3306,
      username: "",
      password: "",
      database: "",
      options: {}
    };
  } catch (err) {
    addPopup("red", "Save failed", String(err));
  }
}

async function onDelete(dbms_id) {
  try {
    const resp = await axios.delete(`${getCurrentApiUrl()}/dbms/${dbms_id}`);
    const ok = parseDataOrPopupError(resp);
    if (ok) {
      addPopup("green", "Deleted", "DBMS entry deleted");
      await fetchList();
    }
  } catch (err) {
    addPopup("red", "Delete failed", String(err));
  }
}

async function onTest(dbms_id) {
  try {
    const ok = await getDataOrPopupError(`/dbms/${dbms_id}/test`);
    addPopup(ok ? "green" : "yellow", "Connectivity", ok ? "Reachable" : "Unreachable");
  } catch (err) {
    addPopup("red", "Test failed", String(err));
  }
}

fetchList();

async function onPickActive(e) {
  activeId.value = e?.dbms_id || null;
  result.value = { columns: [], rows: [] };
  sql.value = "SELECT 1";
  schemas.value = [];
  tables.value = [];
  if (!activeId.value) return;
  try {
    const sc = await getDataOrPopupError(`/dbms/${activeId.value}/schemas`);
    schemas.value = sc || [];
  } catch {}
}

async function loadTables(schema) {
  if (!activeId.value) return;
  activeSchema.value = schema || "";
  try {
    const tb = await getDataOrPopupError(`/dbms/${activeId.value}/tables?schema=${encodeURIComponent(schema||"")}`);
    tables.value = tb || [];
  } catch {}
}

async function runSQL() {
  if (!activeId.value) {
    addPopup("yellow", "Pick a DBMS", "Select a DBMS from the list first");
    return;
  }
  try {
    const resp = await axios.post(`${getCurrentApiUrl()}/dbms/${activeId.value}/query`, { sql: sql.value, params: {}, max_rows: 200, schema: activeSchema.value || null });
    const data = parseDataOrPopupError(resp);
    if (data?.columns) {
      result.value = data;
      addPopup("green", "Success", `Fetched ${data.rows.length} rows`);
    } else {
      addPopup("green", "Success", `Rowcount: ${data.rowcount}`);
      result.value = { columns: [], rows: [] };
    }
  } catch (err) {
    addPopup("red", "Query failed", String(err));
  }
}
</script>

<template>
  <div class="dbms-page">
    <h2>DBMS Management</h2>
    <form class="dbms-form shadow-box" @submit="onSubmit">
      <select v-model="form.db_type">
        <option value="mysql">MySQL</option>
        <option value="postgresql">PostgreSQL</option>
        <option value="oracle">Oracle</option>
        <option value="sqlserver">SQL Server</option>
        <option value="sqlite">SQLite</option>
      </select>
      <input type="text" placeholder="Name" v-model="form.name" required>
      <input v-if="form.db_type!=='sqlite'" type="text" placeholder="Host" v-model="form.host" required>
      <input v-if="form.db_type!=='sqlite'" type="number" placeholder="Port" v-model="form.port" required>
      <input v-if="form.db_type!=='sqlite'" type="text" placeholder="Username" v-model="form.username">
      <input v-if="form.db_type!=='sqlite'" type="password" placeholder="Password" v-model="form.password">
      <input type="text" placeholder="Database (or file path for SQLite)" v-model="form.database">
      <button :disabled="loading">{{ loading ? "Saving..." : "Save" }}</button>
    </form>

    <table class="dbms-table shadow-box">
      <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Host</th>
        <th>Port</th>
        <th>Database</th>
        <th>Actions</th>
      </tr>
      <tr v-for="e in entries">
        <td>{{ e.name }}</td>
        <td>{{ e.db_type }}</td>
        <td>{{ e.host }}</td>
        <td>{{ e.port }}</td>
        <td>{{ e.database }}</td>
        <td>
          <button @click="onTest(e.dbms_id)">Test</button>
          <button @click="onDelete(e.dbms_id)">Delete</button>
        </td>
      </tr>
    </table>

    <div class="dbms-query shadow-box">
      <div class="row">
        <label>Active DBMS</label>
        <select @change="onPickActive(entries.find(x=>x.dbms_id===($event.target.value)))">
          <option value="">Select...</option>
          <option v-for="e in entries" :value="e.dbms_id">{{ e.name }} ({{ e.db_type }})</option>
        </select>
      </div>
      <div class="row">
        <label>Schemas</label>
        <div class="schema-list">
          <button v-for="s in schemas" @click="loadTables(s)">{{ s }}</button>
        </div>
      </div>
      <div class="row">
        <label>Tables</label>
        <div class="table-list">
          <button v-for="t in tables" @click="sql = `SELECT * FROM ${activeSchema ? `${activeSchema}.` : ``}${t} LIMIT 100`">{{ t }}</button>
        </div>
      </div>
      <textarea class="sql-input" v-model="sql" rows="6" placeholder="Write SQL here"></textarea>
      <button class="run-btn" @click="runSQL">Run</button>
      <div class="result" v-if="result.columns.length">
        <table>
          <tr>
            <th v-for="c in result.columns">{{ c }}</th>
          </tr>
          <tr v-for="r in result.rows">
            <td v-for="c in result.columns">{{ r[c] ?? r[Object.keys(r).indexOf(c)] ?? r }}</td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dbms-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dbms-form {
  display: grid;
  grid-template-columns: repeat(6, minmax(140px, 1fr));
  gap: 10px;
  padding: 20px;
  border-radius: 14px;
  background-color: var(--background-color-2);
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.dbms-form input, .dbms-form select, .dbms-form button {
  height: 40px;
  border: none;
  border-radius: 10px;
  outline: none;
  padding: 0 10px;
  color: var(--font-color-primary);
  background-color: var(--background-color-3);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.dbms-table {
  width: 100%;
  background-color: var(--background-color-2);
  color: var(--font-color-primary);
  border-radius: 14px;
  padding: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.dbms-table th, .dbms-table td {
  padding: 8px;
  text-align: left;
}
.dbms-table tr:nth-child(even) td {
  background-color: rgba(255,255,255,0.03);
}
.dbms-query {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  background-color: var(--background-color-2);
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.dbms-query .row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.schema-list, .table-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.schema-list button, .table-list button {
  border: none;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background-color: var(--background-color-3);
  color: var(--font-color-primary);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.sql-input {
  width: 100%;
  border-radius: 10px;
  border: none;
  outline: none;
  background-color: var(--background-color-3);
  color: var(--font-color-primary);
  padding: 10px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.run-btn {
  height: 40px;
  border: none;
  border-radius: 10px;
  background-color: var(--background-color-3);
  color: var(--font-color-primary);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.result table {
  width: 100%;
}
</style>
