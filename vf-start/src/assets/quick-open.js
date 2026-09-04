(()=>{
  'use strict';

  const forms=[
    document.querySelector('.vf-global-search'),
    document.querySelector('.vf-mobile-command-search'),
  ].filter(Boolean);
  if(!forms.length)return;

  const scope=String(document.body?.dataset?.vfScope||'').trim();
  const debounce=(fn,delay)=>{
    let timer=0;
    return(...args)=>{window.clearTimeout(timer);timer=window.setTimeout(()=>fn(...args),delay)};
  };

  const install=(form,index)=>{
    const input=form.querySelector('input[name="q"]');
    if(!input)return;

    const panel=document.createElement('div');
    panel.className='vf-quick-open';
    panel.hidden=true;
    panel.id=`vf-quick-open-${index+1}`;
    panel.setAttribute('role','listbox');
    panel.setAttribute('aria-label','快速打开结果');
    form.append(panel);
    input.setAttribute('aria-controls',panel.id);
    input.setAttribute('aria-expanded','false');
    input.setAttribute('aria-autocomplete','list');

    let rows=[];
    let active=-1;
    let controller=null;
    let requestSerial=0;

    const setOpen=(open)=>{
      panel.hidden=!open;
      input.setAttribute('aria-expanded',open?'true':'false');
      if(!open){active=-1;input.removeAttribute('aria-activedescendant')}
    };

    const fullSearchUrl=(query)=>{
      const params=new URLSearchParams();
      if(scope==='public'||scope==='private')params.set('scope',scope);
      params.set('q',query);
      return `surfaces.php?${params.toString()}`;
    };

    const syncActive=()=>{
      panel.querySelectorAll('[data-quick-open-index]').forEach((node,i)=>{
        const selected=i===active;
        node.classList.toggle('active',selected);
        node.setAttribute('aria-selected',selected?'true':'false');
        if(selected){
          input.setAttribute('aria-activedescendant',node.id);
          node.scrollIntoView({block:'nearest'});
        }
      });
      if(active<0)input.removeAttribute('aria-activedescendant');
    };

    const openRow=(row)=>{
      const url=String(row?.open_url||'').trim();
      if(!url)return;
      const opened=window.open(url,'_blank','noopener,noreferrer');
      if(opened)opened.opener=null;
      setOpen(false);
      input.select();
    };

    const render=(query,resultRows)=>{
      rows=Array.isArray(resultRows)?resultRows:[];
      active=rows.length?0:-1;
      panel.replaceChildren();

      if(!rows.length){
        const empty=document.createElement('div');
        empty.className='vf-quick-open-empty';
        empty.textContent='没有即时结果；按 Enter 查看完整搜索';
        panel.append(empty);
      }else{
        rows.forEach((row,i)=>{
          const button=document.createElement('button');
          button.type='button';
          button.className='vf-quick-open-item';
          button.id=`${panel.id}-item-${i}`;
          button.dataset.quickOpenIndex=String(i);
          button.setAttribute('role','option');
          button.setAttribute('aria-selected',i===active?'true':'false');

          const copy=document.createElement('span');
          copy.className='vf-quick-open-copy';
          const title=document.createElement('strong');
          title.textContent=String(row.title||'未命名资源');
          const meta=document.createElement('small');
          const bits=[String(row.surface_label||'资源')];
          if(String(row.context||'').trim())bits.push(String(row.context));
          if(row.private)bits.push('私人');
          meta.textContent=bits.join(' · ');
          copy.append(title,meta);

          const arrow=document.createElement('span');
          arrow.className='vf-quick-open-arrow';
          arrow.textContent='↗';
          button.append(copy,arrow);
          button.addEventListener('mouseenter',()=>{active=i;syncActive()});
          button.addEventListener('click',()=>openRow(row));
          panel.append(button);
        });
      }

      const footer=document.createElement('a');
      footer.className='vf-quick-open-all';
      footer.href=fullSearchUrl(query);
      footer.textContent='查看全部搜索结果 →';
      panel.append(footer);
      setOpen(true);
      syncActive();
    };

    const renderStatus=(message)=>{
      rows=[];active=-1;panel.replaceChildren();
      const status=document.createElement('div');
      status.className='vf-quick-open-empty';
      status.textContent=message;
      panel.append(status);
      setOpen(true);
    };

    const queryNow=async()=>{
      const query=String(input.value||'').trim();
      const serial=++requestSerial;
      if(query===''){
        controller?.abort();
        setOpen(false);
        return;
      }
      controller?.abort();
      controller=new AbortController();
      try{
        const params=new URLSearchParams({q:query,limit:'8'});
        if(scope==='public'||scope==='private')params.set('scope',scope);
        const response=await fetch(`quick-search.php?${params.toString()}`,{
          credentials:'same-origin',
          headers:{Accept:'application/json'},
          signal:controller.signal,
        });
        const body=await response.json().catch(()=>({ok:false}));
        if(serial!==requestSerial)return;
        if(!response.ok||!body.ok)throw new Error('quick search failed');
        render(query,body.results||[]);
      }catch(error){
        if(error?.name==='AbortError')return;
        if(serial!==requestSerial)return;
        renderStatus('即时搜索暂时不可用；按 Enter 使用完整搜索');
      }
    };
    const delayedQuery=debounce(queryNow,110);

    input.addEventListener('input',delayedQuery);
    input.addEventListener('focus',()=>{
      if(String(input.value||'').trim()!=='')delayedQuery();
    });
    input.addEventListener('keydown',event=>{
      if(event.key==='Escape'){
        if(!panel.hidden){event.preventDefault();setOpen(false)}
        return;
      }
      if(panel.hidden||!rows.length)return;
      if(event.key==='ArrowDown'){
        event.preventDefault();active=(active+1)%rows.length;syncActive();return;
      }
      if(event.key==='ArrowUp'){
        event.preventDefault();active=active<=0?rows.length-1:active-1;syncActive();return;
      }
      if(event.key==='Enter'&&active>=0&&rows[active]){
        event.preventDefault();openRow(rows[active]);
      }
    });

    document.addEventListener('pointerdown',event=>{
      if(!form.contains(event.target))setOpen(false);
    });
  };

  const shortcutInput=()=>{
    const inputs=forms
      .map(form=>form.querySelector('input[name="q"]'))
      .filter(Boolean);
    return inputs.find(input=>input.offsetParent!==null)||inputs[0]||null;
  };

  document.addEventListener('keydown',event=>{
    if(!(event.metaKey||event.ctrlKey)||event.altKey||String(event.key||'').toLowerCase()!=='k')return;
    const input=shortcutInput();
    if(!input)return;
    event.preventDefault();
    input.focus();
    input.select();
  });

  forms.forEach(install);
})();