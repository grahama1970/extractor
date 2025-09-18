const puppeteer=require('puppeteer');
(async()=>{
 const url=process.env.URL||'http://127.0.0.1:8080/main';
 const b=await puppeteer.launch({headless:'new',args:['--no-sandbox']});
 const p=await b.newPage();
 await p.goto(url,{waitUntil:'domcontentloaded'});
 await new Promise(r=>setTimeout(r,1000));
 const sels=['[data-testid="top-toolbar"]','[data-testid="pager-prev"]','[data-testid="page-number"]','[data-testid="page-slider"]','[data-testid="filter-owner"]'];
 const out={};
 for(const s of sels){ out[s]=!!(await p.$(s)); }
 console.log(JSON.stringify(out,null,2));
 await b.close();
})();
