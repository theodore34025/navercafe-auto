'use strict';
const $ = id => document.getElementById(id);
let active = false, imageURL = null, queue = Promise.resolve();
function message(text, error = false) { if (!text) return; $('status').textContent = text; $('status').classList.toggle('error', error); }
function running(value) { active = value; ['save','close','insert'].forEach(id => $(id).disabled = !value); if (!value) { $('screen').hidden = true; $('empty').hidden = false; } }
async function request(path, options = {}) {
  const response = await fetch(path, {cache:'no-store', ...options});
  if (response.status === 401 && path !== '/auth') { running(false); $('auth-panel').hidden = false; $('control-panel').hidden = true; throw new Error('접속이 만료되었습니다. 접속 코드를 다시 입력하세요.'); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || '요청에 실패했습니다.');
  return data;
}
function action(data) {
  // Preserve the ordering of mouse, keyboard and save events.
  const operation = queue.then(async () => {
    const result = await request('/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    message(result.message);
    return result;
  });
  queue = operation.catch(error => message(error.message, true));
  return operation;
}
async function refresh() {
  if (active) {
    try {
      const response = await fetch('/screen', {cache:'no-store'});
      if (response.status === 401) { running(false); message('접속이 만료되었습니다. 페이지를 새로고침하고 다시 연결하세요.', true); }
      else if (response.status === 409) { running(false); message('원격 브라우저가 종료되었습니다. 다시 열어주세요.'); }
      else if (response.ok) {
        const next = URL.createObjectURL(await response.blob());
        $('screen').src = next; $('screen').hidden = false; $('empty').hidden = true;
        if (imageURL) URL.revokeObjectURL(imageURL);
        imageURL = next;
      }
    } catch (_) { message('서버 연결을 확인하세요.', true); }
  }
  setTimeout(refresh, 500);
}
$('auth-form').addEventListener('submit', async event => {
  event.preventDefault(); const token = $('token').value; $('token').value = '';
  try {
    const result = await request('/auth', {method:'POST', body:new URLSearchParams({token})});
    $('auth-panel').hidden = true; $('control-panel').hidden = false; message(result.message);
    const state = await request('/status'); running(state.running);
  } catch (error) { message(error.message, true); }
});
$('start').onclick = async () => {
  if (active && !confirm('현재 로그인 화면을 닫고 처음부터 다시 여시겠습니까?')) return;
  $('start').disabled = true; message('네이버 로그인 화면을 여는 중입니다…');
  try { await action({type:'start'}); running(true); } catch (_) { running(false); }
  finally { $('start').disabled = false; }
};
$('save').onclick = async () => { $('save').disabled = true; try { await action({type:'save'}); } catch (_) {} finally { $('save').disabled = !active; } };
$('close').onclick = async () => { try { await action({type:'close'}); running(false); } catch (_) {} };
$('text-form').addEventListener('submit', async event => {
  event.preventDefault(); const text = $('text').value; $('text').value = '';
  if (text) { try { await action({type:'text', text}); $('screen').focus({preventScroll:true}); } catch (_) {} }
});
function pointer(event, operation) {
  if (!active || event.button > 0) return;
  event.preventDefault(); const rect = $('screen').getBoundingClientRect();
  const x = Math.max(0, Math.min(1279, (event.clientX - rect.left) * 1280 / rect.width));
  const y = Math.max(0, Math.min(799, (event.clientY - rect.top) * 800 / rect.height));
  action({type:'mouse', operation, x, y}).catch(() => {});
}
$('screen').addEventListener('pointerdown', event => { $('screen').focus({preventScroll:true}); $('screen').setPointerCapture(event.pointerId); pointer(event, 'down'); });
$('screen').addEventListener('pointerup', event => pointer(event, 'up'));
let lastMove = 0;
$('screen').addEventListener('pointermove', event => { if (event.buttons && Date.now()-lastMove > 60) { lastMove = Date.now(); pointer(event, 'move'); } });
$('screen').addEventListener('pointercancel', event => pointer(event, 'up'));
$('screen').addEventListener('wheel', event => { event.preventDefault(); action({type:'wheel', delta:event.deltaY}).catch(() => {}); }, {passive:false});
$('screen').addEventListener('keydown', event => {
  if (['Shift','Control','Alt','Meta','Process','Dead','Unidentified'].includes(event.key) || event.isComposing) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'v') return; // paste handler below
  event.preventDefault();
  const modifiers = [event.ctrlKey?'Control':null,event.metaKey?'Meta':null,event.altKey?'Alt':null,event.shiftKey?'Shift':null].filter(Boolean);
  const key = event.key === ' ' ? 'Space' : event.key;
  const payload = event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey ? {type:'text',text:event.key} : {type:'key',key:[...modifiers,key].join('+')};
  action(payload).catch(() => {});
});
$('screen').addEventListener('paste', event => { event.preventDefault(); const text = event.clipboardData.getData('text/plain'); if(text) action({type:'text',text}).catch(() => {}); });
(async () => { try { const state = await request('/status'); $('auth-panel').hidden = true; $('control-panel').hidden = false; running(state.running); message(state.saved?'로그인 세션이 저장되어 있습니다.':'연결되었습니다. 로그인 화면을 열어주세요.'); } catch (_) { message('접속 코드를 입력하세요.'); } refresh(); })();
