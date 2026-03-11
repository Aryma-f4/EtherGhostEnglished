import axios from "axios"
import { popupsRef, currentSettings } from "./store"
import { ref, shallowRef } from "vue"

class UserError extends Error {
  constructor(message) {
    super(message);
    this.name = "UserError"
    this.message = `Client error: ${message}`
  }
}

class ServerError extends Error {
  constructor(message) {
    super(message);
    this.name = "ServerError"
    this.message = `Server error: ${message}`
  }
}

class TargetError extends Error {
  constructor(message) {
    super(message);
    this.name = "TargetError";
    this.message = `Target error: ${message}`
  }
}

export async function joinPath(folder, entry) {
  return await getDataOrPopupError("/utils/join_path", {
    params: {
      folder: folder,
      entry: entry
    }
  })
}

export function getCurrentApiUrl() {
  return window.location.origin.includes("5173") ? `http://${window.location.hostname}:8022` : window.location.origin
}

export function doAssert(result, msg) {
  if (result) {
    return
  }
  if (msg) {
    throw Error(msg)
  } else {
    throw Error("Assertion failed, message is not provided")
  }
}

export function addPopup(color, title, msg) {
  popupsRef.value.addPopup(color, title, msg)
}

export function parseDataOrPopupError(resp) {
  if (resp.data.code != 0) {
    let title = `Unknown error: ${resp.data.code}`
    let errorClass
    if (resp.data.code == -400) {
      title = "Client Error"
      errorClass = UserError
    } else if (resp.data.code == -500) {
      title = "Server Error"
      errorClass = ServerError
    } else if (resp.data.code == -600) {
      title = "Target Error"
      errorClass = TargetError
    } else {
      title = "Error"
      errorClass = Error
    }
    addPopup("red", title, resp.data.msg)
    throw new errorClass(resp.data.msg)
  }
  return resp.data.data
}


export async function getDataOrPopupError(uri, config) {
  let url = `${getCurrentApiUrl()}${uri}`
  let resp
  try {
    resp = await axios.get(url, config)
  } catch (e) {
    addPopup("red", "Request to server failed", `Unable to request ${uri}. Is the server running?`)
    throw e
  }
  return parseDataOrPopupError(resp)
}

export async function getDataOrSilentError(uri, config) {
  let url = `${getCurrentApiUrl()}${uri}`
  let resp
  try {
    resp = await axios.get(url, config)
  } catch (e) {
    return null
  }
  try {
    return parseDataOrPopupError(resp)
  } catch {
    return null
  }
}

export async function postDataOrPopupError(uri, data, config = undefined) {
  let url = `${getCurrentApiUrl()}${uri}`
  let resp
  try {
    resp = await axios.post(url, data, config)
  } catch (e) {
    addPopup("red", "Request to server failed", `Unable to request ${uri}. Is the server running?`)
    throw e
  }
  return parseDataOrPopupError(resp)
}


export function ClickMenuManager(items, handleSelected) {
  const showClickMenu = ref(false)
  const clickMenuX = ref(0)
  const clickMenuY = ref(0)

  function onShowClickMenu(event) {
    event.preventDefault()
    showClickMenu.value = true
    clickMenuX.value = event.clientX;
    clickMenuY.value = event.clientY;
  }
  function onclickEvent(item) {
    showClickMenu.value = false
    handleSelected(item)
  }
  function onRemove(_) {
    showClickMenu.value = false
  }
  return {
    "items": shallowRef(items),
    "show": showClickMenu,
    "onshow": onShowClickMenu,
    "onclick": onclickEvent,
    "onremove": onRemove,
    "x": clickMenuX,
    "y": clickMenuY,
  }
}


export function readableFileSize(fileSize) {
  if (fileSize == -1) {
    return "? KB"
  }
  let units = ["B", "KiB", "MiB", "GiB", "TiB"]
  let diff = 1024
  if (currentSettings.filesizeUnit == 1000) {
    units = ["B", "KB", "MB", "GB", "TB"]
    diff = 1000
  }
  if (fileSize < diff) {
    return `${fileSize}B`
  }
  for (let unit of units) {
    if (fileSize <= diff || unit == units[units.length - 1]) {
      return `${fileSize.toFixed(2)}${unit}`
    }
    fileSize /= diff
  }
}
