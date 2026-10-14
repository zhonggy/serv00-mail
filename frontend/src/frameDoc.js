// 邮件正文 iframe 高度自适应：向 srcdoc 注入上报脚本，父页面监听 postMessage 设置 iframe 高度。
// 沙盒仅放行脚本（allow-scripts），邮件 JS 跑在隔离域，只能通过 postMessage 上报高度。

export function frameDoc(html) {
  return (html || '') + `<script>
(function(){
  function h(){
    var d=document.documentElement,b=document.body;
    return Math.max(
      b?b.scrollHeight:0, b?b.offsetHeight:0,
      d?d.scrollHeight:0, d?d.offsetHeight:0
    );
  }
  function p(){ try{ parent.postMessage({__sm_h:h()},'*'); }catch(e){} }
  function w(){
    p();
    try{
      var imgs=document.images;
      for(var i=0;i<imgs.length;i++){
        if(!imgs[i].complete){ imgs[i].addEventListener('load',p); imgs[i].addEventListener('error',p); }
      }
    }catch(e){}
  }
  if(document.readyState==='complete'){ w(); }
  else{ window.addEventListener('load',w); }
  setTimeout(w,600); setTimeout(w,1600); setTimeout(w,3200);
})();
<\/script>`
}

// 父页面收到高度后设置 iframe 高度：不设视口上限，完全按内容来，超长由抽屉滚动承载
export function fitFrame(frameRef, data) {
  if (data && typeof data.__sm_h === 'number' && frameRef.value) {
    const h = Math.max(240, Math.min(data.__sm_h + 24, 12000))
    frameRef.value.style.height = h + 'px'
  }
}
