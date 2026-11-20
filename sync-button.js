// 노션 동기화 버튼
// - 토큰이 없으면: GitHub Actions 실행 화면으로 가는 바로가기
// - 토큰을 이 브라우저에 저장해 두면: 버튼 한 번으로 동기화 실행 → 끝나면 새로고침
// 토큰은 코드나 저장소에 들어가지 않고, 사용자 브라우저의 localStorage에만 저장된다.
(function(){
  const REPO = "musicinsun/consensus-note", WF = "sync.yml", KEY = "cn-sync-token";
  const ACTIONS_URL = `https://github.com/${REPO}/actions/workflows/${WF}`;
  const TOKEN_URL = "https://github.com/settings/personal-access-tokens/new";
  const $ = id => document.getElementById(id);
  const panel = $("sync-panel"), msg = $("sync-msg"), dateIn = $("sync-date"), runBtn = $("sync-run");
  if (!panel) return;

  const getTok = () => { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } };
  const setTok = v => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} };

  // 한국 시간 기준 오늘 날짜 (YYMMDD)
  function todayKST(){
    const k = new Date(Date.now() + 9 * 3600e3);
    return String(k.getUTCFullYear() % 100).padStart(2, "0") + String(k.getUTCMonth() + 1).padStart(2, "0") + String(k.getUTCDate()).padStart(2, "0");
  }

  function refresh(){
    const has = !!getTok();
    $("sync-oneclick").hidden = !has;
    $("sync-setup").hidden = has;
    runBtn.textContent = has ? "동기화 실행" : "GitHub에서 실행하기 ↗";
  }

  function say(t, kind){ msg.textContent = t; msg.className = "sync-msg " + (kind || ""); }

  async function gh(path, opts){
    const r = await fetch("https://api.github.com/repos/" + REPO + path, Object.assign({}, opts, {
      headers: {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + getTok(), "X-GitHub-Api-Version": "2022-11-28"}
    }));
    if (r.status === 401 || r.status === 403) throw new Error("토큰이 거절됐어요. 권한(Actions 읽기·쓰기)과 저장소 선택을 확인해 주세요.");
    if (!r.ok && r.status !== 204) throw new Error("GitHub 응답 오류 (" + r.status + ")");
    return r.status === 204 ? null : r.json();
  }

  async function run(){
    const d = dateIn.value.trim();
    if (d && !/^\d{6}(,\d{6})*$/.test(d)) { say("날짜는 261120 처럼 6자리로 적어 주세요. 여러 날은 쉼표로 구분해요.", "err"); return; }
    if (!getTok()) { window.open(ACTIONS_URL, "_blank", "noopener"); say("GitHub에서 'Run workflow'를 누르고 날짜 칸에 " + (d || todayKST()) + " 를 넣어 주세요."); return; }
    runBtn.disabled = true;
    try {
      const started = Date.now() - 5000;
      say("동기화를 요청하는 중…");
      await gh(`/actions/workflows/${WF}/dispatches`, {method: "POST", body: JSON.stringify({ref: "main", inputs: {only_dates: d}})});
      say(d ? `${d} 동기화 중… (보통 1~2분)` : "전체 동기화 중… (최대 15분)");
      let run = null;
      for (let i = 0; i < 120; i++) {
        await new Promise(res => setTimeout(res, 10000));
        const list = await gh(`/actions/workflows/${WF}/runs?event=workflow_dispatch&per_page=3`);
        run = (list.workflow_runs || []).find(x => new Date(x.created_at).getTime() >= started) || run;
        if (!run) continue;
        if (run.status === "completed") break;
        say(`${d || "전체"} 동기화 중… ${run.status === "queued" ? "(앞선 동기화가 끝나길 기다리는 중)" : ""}`);
      }
      if (!run || run.status !== "completed") { say("아직 끝나지 않았어요. 잠시 뒤 새로고침해 주세요.", "err"); return; }
      if (run.conclusion !== "success") { say("동기화가 실패했어요. GitHub Actions 기록을 확인해 주세요.", "err"); return; }
      // 사이트(GitHub Pages)에 반영되기까지 1분 정도 걸림
      for (let s = 60; s > 0; s -= 5) { say(`동기화 완료! 사이트 반영을 기다리는 중… ${s}초`, "ok"); await new Promise(res => setTimeout(res, 5000)); }
      say("반영 완료. 새로고침할게요.", "ok");
      location.reload();
    } catch (e) {
      say(e.message, "err");
    } finally {
      runBtn.disabled = false;
    }
  }

  $("sync-open").addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden && !dateIn.value) dateIn.value = todayKST();
    refresh();
  });
  runBtn.addEventListener("click", run);
  $("sync-save").addEventListener("click", () => {
    const v = $("sync-token").value.trim();
    if (!/^(github_pat_|ghp_)/.test(v)) { say("github_pat_ 로 시작하는 토큰을 붙여넣어 주세요.", "err"); return; }
    setTok(v); $("sync-token").value = ""; refresh(); say("이 브라우저에 저장했어요. 이제 '동기화 실행'을 누르면 바로 돌아가요.", "ok");
  });
  $("sync-forget").addEventListener("click", () => { setTok(""); refresh(); say("이 브라우저에서 토큰을 지웠어요."); });
  $("sync-actions").href = ACTIONS_URL;
  $("sync-newtoken").href = TOKEN_URL;
})();
