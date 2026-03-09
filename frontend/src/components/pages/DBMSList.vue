<script setup>
import { ref } from "vue";
import { addPopup, getDataOrPopupError, parseDataOrPopupError, getCurrentApiUrl, postDataOrPopupError } from "@/assets/utils";
import axios from "axios";
import { useRouter } from "vue-router";

const router = useRouter();
const entries = ref([]);
const loading = ref(false);
const showForm = ref(false);
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

async function onDelete(dbms_id) {
  try {
    const resp = await axios.delete(`${getCurrentApiUrl()}/dbms/${dbms_id}`);
    const ok = parseDataOrPopupError(resp);
    if (ok) {
      addPopup("green", "Deleted", "DBMS deleted");
      await fetchList();
    }
  } catch (err) {
    addPopup("red", "Delete failed", String(err));
  }
}

function openDetail(id) {
  router.push(`/dbms/${id}`);
}

function openCreate() {
  showForm.value = true;
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
}

function openEdit(e) {
  showForm.value = true;
  form.value = {
    dbms_id: e.dbms_id,
    name: e.name || "",
    db_type: e.db_type || "mysql",
    host: e.host || "",
    port: e.port || 3306,
    username: e.username || "",
    password: "",
    database: e.database || "",
    options: e.options || {}
  };
}

async function saveForm(e) {
  e.preventDefault();
  try {
    await postDataOrPopupError("/dbms", form.value);
    addPopup("green", "Saved", "DBMS saved");
    showForm.value = false;
    await fetchList();
  } catch (err) {
    addPopup("red", "Save failed", String(err));
  }
}

fetchList();
</script>

<template>
  <div class="dbms-list">
    <div class="header">
      <h2>DBMS</h2>
      <button class="primary" @click="openCreate">New Connection</button>
    </div>
    <div v-if="showForm" class="form-card">
      <form class="form-grid" @submit="saveForm">
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
        <div class="form-actions">
          <button type="submit" class="primary">Save</button>
          <button type="button" @click="showForm=false">Cancel</button>
        </div>
      </form>
    </div>
    <div class="cards">
      <div class="card" v-for="e in entries" :key="e.dbms_id">
        <div class="title">{{ e.name }}</div>
        <div class="meta">{{ e.db_type.toUpperCase() }} • {{ e.host }}:{{ e.port }}</div>
        <div class="actions">
          <button @click="openDetail(e.dbms_id)">Open</button>
          <button @click="openEdit(e)">Edit</button>
          <button @click="onDelete(e.dbms_id)">Delete</button>
        </div>
      </div>
      <div v-if="!entries.length && !loading" class="empty">No DBMS yet</div>
    </div>
  </div>
</template>

<style scoped>
.dbms-list { display: flex; flex-direction: column; gap: 16px; }
.header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.primary { background-color: #2f7a3e; color: #fff; border: none; border-radius: 10px; padding: 0 14px; height: 36px; }
.form-card { background-color: var(--background-color-2); border-radius: 14px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); }
.form-grid { display: grid; grid-template-columns: repeat(6, minmax(140px, 1fr)); gap: 10px; }
.form-grid input, .form-grid select, .form-grid button {
  height: 40px; border: none; border-radius: 10px; outline: none; padding: 0 10px;
  color: var(--font-color-primary); background-color: var(--background-color-3);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.form-actions { display: flex; gap: 8px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.card {
  background-color: var(--background-color-2);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.title { font-size: 16px; font-weight: 600; }
.meta { opacity: 0.8; margin-top: 4px; }
.actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.actions button {
  height: 36px; border: none; border-radius: 10px;
  background-color: var(--background-color-3); color: var(--font-color-primary);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.empty { opacity: 0.7; }
@media (max-width: 900px) {
  .form-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
}
@media (max-width: 560px) {
  .header { flex-direction: column; align-items: flex-start; }
  .form-grid { grid-template-columns: 1fr; }
  .cards { grid-template-columns: 1fr; }
}
</style>
