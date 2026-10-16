/* Poll persisted jobs without replacing the document or the user's selection. */
(() => {
  const view=document.getElementById('product-batch');if(!view)return;
  const form=document.getElementById('product-batch-form');
  const boxes=()=>[...form.querySelectorAll('[name="product_ids"]')];
  document.getElementById('select-all').onclick=()=>boxes().forEach(b=>b.checked=true);
  document.getElementById('select-none').onclick=()=>boxes().forEach(b=>b.checked=false);
  document.querySelectorAll('[data-product-row]').forEach(row=>row.addEventListener('click',e=>{
    if(!e.target.closest('a,button,input,label'))location.href=`/products/${row.dataset.productRow}`;
  }));
  form.addEventListener('submit',()=>form.querySelectorAll('[type="submit"]').forEach(b=>b.disabled=true));
  const notice=document.getElementById('progress-notice');
  async function poll(){
    try{
      const response=await fetch(view.dataset.progressUrl,{cache:'no-store'});
      if(!response.ok)throw new Error('progress unavailable');
      const state=await response.json();
      for(const row of state.rows){
        const tr=document.querySelector(`[data-product-row="${row.id}"]`);if(!tr)continue;
        for(const key of ['status_label','progress_label','specs_count','photos_count','color','readiness_label','reason']){
          const cell=tr.querySelector(`[data-field="${key}"]`);if(cell)cell.textContent=row[key];
        }
      }
      for(const [key,value]of Object.entries(state.summary))document.querySelectorAll(`[data-summary="${key}"]`).forEach(el=>el.textContent=value);
      document.getElementById('batch-progress').value=state.summary.completed;
      document.getElementById('batch-heading').textContent=state.summary.completed===state.summary.total?'Результаты обработки':'Обработка товаров';
      notice.textContent='Обновлено: '+new Date().toLocaleTimeString('ru-RU');
    }catch(_){notice.textContent='Не удалось обновить прогресс. Повторяем через 3 секунды.';}
    window.setTimeout(poll,3000);
  }
  window.setTimeout(poll,3000);
})();
