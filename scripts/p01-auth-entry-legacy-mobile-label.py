from pathlib import Path
import os
root=Path(os.environ['P01_ROOT'])
p=root/'src/index.php'
s=p.read_text(encoding='utf-8')
old='<button id="mobileAccount" class="mobile-nav-btn"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg><span>管理</span></button>'
new='<button id="mobileAccount" class="mobile-nav-btn"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg><span>登录</span></button>'
if s.count(old)!=1: raise SystemExit(f'mobileAccount markup anchor mismatch: {s.count(old)}')
s=s.replace(old,new)
old2="  $('#loginButton').innerHTML=icon(auth?'logout':'login',15)+'<span>'+(auth?'退出':'登录')+'</span>';"
new2="  $('#loginButton').innerHTML=icon(auth?'logout':'login',15)+'<span>'+(auth?'退出':'登录')+'</span>';\n  var mobileAccountLabel=$('#mobileAccount span');if(mobileAccountLabel)mobileAccountLabel.textContent=auth?'管理':'登录';"
if s.count(old2)!=1: raise SystemExit(f'renderHeader anchor mismatch: {s.count(old2)}')
s=s.replace(old2,new2)
p.write_text(s,encoding='utf-8')
