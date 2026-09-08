from pathlib import Path
from urllib.parse import quote
# Original small illustrations. Shared one-pixel edges and a restrained palette.
folder='<path d="M2 8h11l3 4h14v17H2z" fill="#b78625"/><path d="M3 7h10l3 4h13v16H3z" fill="#f4ce67" stroke="#735321"/><path d="M4 13h27l-4 15H1z" fill="#ffdc7b" stroke="#735321"/><path d="M5 14h24M4 15v9" fill="none" stroke="#fff3bb"/>'
monitor='<path d="M3 2h25v21H3z" fill="#c0c0c0" stroke="#292929"/><path d="M5 4h21v16H5z" fill="#748d9c"/><path d="M6 5h19v13H6z" fill="#194c83" stroke="#222"/><path d="M7 6h17v2H7z" fill="#62b9df"/><path d="M8 8h4v8H8z" fill="#3291be"/><path d="M13 23h6v3h8v3H5v-3h8z" fill="#aaa" stroke="#333"/><path d="M4 3h22M6 27h19" stroke="white"/>'
paper='<path d="M6 1h15l6 6v23H6z" fill="white" stroke="#333"/><path d="M21 1v7h6" fill="#d4d0c8" stroke="#555"/><path d="M9 12h14M9 16h14M9 20h11M9 24h13" stroke="#808080"/>'
globe='<circle cx="16" cy="16" r="13" fill="#246aad" stroke="#173650"/><path d="M5 10h22M3 17h26M6 24h20M16 3c-10 8-10 19 0 26M16 3c10 8 10 19 0 26" fill="none" stroke="#82cbd6"/><path d="M7 6l7-2 3 5-5 4-6-2zM18 16l7-3 3 6-7 7-4-4z" fill="#63a650" stroke="#346531"/>'
icons={
'folder':folder,'files':folder+'<path d="M11 5h10l4 4v11H11z" fill="#fff" stroke="#777"/><path d="M14 10h8M14 13h8M14 16h6" stroke="#4870a0"/>',
'computer':monitor,'devices':monitor+'<path d="M1 24h10v6H1z" fill="#438fa9" stroke="#222"/><path d="M1 25h9" stroke="white"/>',
'browser':globe+'<path d="M3 26C0 14 17 3 30 7" fill="none" stroke="#f3c443" stroke-width="3"/>',
'search':folder+'<circle cx="18" cy="13" r="7" fill="#e0f4ff" stroke="#234865" stroke-width="2"/><path d="M23 19l7 9" stroke="#27394b" stroke-width="4"/><path d="M15 9l-2 4" stroke="white" stroke-width="2"/>',
'editor':paper+'<path d="M10 13l-5 4 5 4M23 13l5 4-5 4M19 11l-5 12" fill="none" stroke="#153f88" stroke-width="2"/>',
'notes': '<path d="M5 2h22v28H5z" fill="#ffffd1" stroke="#59553c"/><path d="M7 3v26" stroke="#bd6363"/><path d="M9 9h15M9 14h15M9 19h12M9 24h14" stroke="#799aaf"/><path d="M6 1v5M11 1v5M16 1v5M21 1v5M26 1v5" stroke="#555" stroke-width="2"/>',
'calculator':'<rect x="5" y="1" width="23" height="29" fill="#bcbcb4" stroke="#333"/><path d="M7 3h19v7H7z" fill="#d8e8cc" stroke="#626859"/><path d="M9 12h4v4H9zM16 12h4v4h-4zM9 19h4v4H9zM16 19h4v4h-4zM9 25h4v3H9zM16 25h4v3h-4z" fill="#efefeb" stroke="#777"/><path d="M23 12h3v4h-3zM23 19h3v9h-3z" fill="#184b92"/>',
'cad':'<path d="M3 1h24v29H3z" fill="#e9f3fa" stroke="#425b70"/><path d="M6 5h18v15H6z" fill="none" stroke="#487aa2"/><circle cx="11" cy="10" r="2" fill="white" stroke="#305b7f"/><path d="M13 25L29 9v16z" fill="#edc257" stroke="#775619"/><path d="M21 21l5-5v5z" fill="#edf2e8" stroke="#775619"/>',
'sftp':folder+'<path d="M7 7h17l-5-4M24 7l-5 4" fill="none" stroke="#216f36" stroke-width="3"/><path d="M24 23H7l5-4M7 23l5 4" fill="none" stroke="#1e5796" stroke-width="3"/>',
'activities':monitor+'<path d="M6 13h5l3-5 4 9 3-6h4" fill="none" stroke="#92ff7d" stroke-width="2"/>',
'settings':'<path d="M2 5h28v23H2z" fill="#d1d1ca" stroke="#333"/><path d="M3 6h26v5H3z" fill="#23538c"/><path d="M8 13v12M16 13v12M24 13v12" stroke="#6b6b65"/><path d="M5 16h6v4H5zM13 20h6v4h-6zM21 13h6v4h-6z" fill="#f3f3ed" stroke="#444"/>',
'users':'<circle cx="12" cy="9" r="6" fill="#e6bb8b" stroke="#695039"/><path d="M2 28v-7c0-9 20-9 20 0v7z" fill="#2c6395" stroke="#263f60"/><circle cx="24" cy="13" r="4" fill="#f2c894" stroke="#695039"/><path d="M21 21c3-5 9-1 9 3v4h-7" fill="#628446" stroke="#354e32"/>',
'help':'<path d="M5 2h20l3 4v25H5z" fill="#514786" stroke="#292644"/><path d="M6 3h17v25H6z" fill="#675ca4"/><path d="M24 4v24h3M8 30h18" stroke="#d6d1ed"/><path d="M11 11c0-7 12-7 12 0 0 4-6 4-6 8M17 22v2" fill="none" stroke="white" stroke-width="3"/>',
'recycle':'<path d="M7 6h20l-3 24H10z" fill="#d6e7e8" stroke="#3e6062"/><path d="M12 9l1 17M18 9v17M24 9l-2 17" stroke="#9eb6b8"/><ellipse cx="17" cy="6" rx="11" ry="3" fill="#fff" stroke="#3e6062"/><path d="M14 13l4-3 4 4-3 1M23 18l-1 6-5-1 1-3M13 24l-4-5 3-4 2 3" fill="none" stroke="#2376a6" stroke-width="2"/>',
'logout':'<path d="M6 2h18v28H6z" fill="#bc864d" stroke="#513919"/><path d="M8 4l11 3v21L8 30z" fill="#e5b371" stroke="#624622"/><path d="M16 17v3" stroke="#333" stroke-width="2"/><path d="M18 15h12l-5-5M30 15l-5 5" fill="none" stroke="#ac2929" stroke-width="3"/>',
'run':'<path d="M2 6h28v22H2z" fill="#efefeb" stroke="#333"/><path d="M3 7h26v5H3z" fill="#24558f"/><path d="M5 16l4 3-4 3M12 22h7" fill="none" stroke="#333" stroke-width="2"/>',
'link':paper+'<path d="M1 20h13v11H1z" fill="white" stroke="#555"/><path d="M3 28v-5h7l-3-3M10 23l-3 3" fill="none" stroke="#153d91" stroke-width="2"/>',
'status':monitor+'<path d="M7 16v-5h3v5M13 16V7h3v9M19 16v-7h3v7" fill="#7fd897"/>',
'file':paper,'programs':folder+'<path d="M11 13h16v11H11z" fill="#eee" stroke="#333"/><path d="M12 14h14v3H12z" fill="#255591"/><path d="M13 20h3M18 20h6" stroke="#808080"/>',
'save':'<path d="M3 2h24l3 3v25H3z" fill="#294f83" stroke="#25313d"/><path d="M7 3h16v10H7z" fill="#c2c7c9"/><path d="M18 4h3v7h-3z" fill="#596775"/><path d="M7 18h19v11H7z" fill="#fff"/><path d="M10 21h13M10 24h13" stroke="#999"/>',
}
alias={'forms':'file','content':'file','home':'computer','network':'devices','controls':'settings','preferences':'settings','analysis':'status','details':'file','profile':'users','messages':'notes','lock':'users','shutdown':'computer','add':'link','password':'users'}
css=['/* Original classic icons, authored for this project. */',':root {']
for key,value in icons.items():
 svg='<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'+value+'</svg>'
 css.append('--icon-'+key+':url("data:image/svg+xml,'+quote(svg,safe='')+'");')
css+=['}', '.win2k-pixel-icon { width:32px!important;height:32px!important;min-width:32px!important;flex-shrink:0;filter:none!important;background:var(--icon-file) center/contain no-repeat!important; }','.win2k-pixel-icon::before,.win2k-pixel-icon::after,.win2k-pixel-icon i { display:none!important; }']
for key in list(icons)+list(alias):css.append('.win2k-icon-'+key+' { background-image:var(--icon-'+alias.get(key,key)+')!important; }')
Path('assets/classic-icons.css').write_text('\n'.join(css)+'\n')
