/** Tailwind config for the SnapSell demo web app (demo/ directory).
 *  Regenerate demo/tailwind.css from demo/ with:
 *    npx --yes tailwindcss@3.4.17 -i tailwind-input.css -o tailwind.css --content ./index.html --minify
 *  The committed tailwind.css is the compiled output for the current
 *  demo/index.html; re-run the command after any class change. */
module.exports = {
  content: ['./index.html'],
  theme: {
    extend: {
      colors: { paper:'#faf7f1', surface:'#fffdf8', ink:'#211a13', ink2:'#3a322a', muted:'#6f6558', line:'#e6ddcf', line2:'#d8cbb8', accent:'#b23a12', accentdark:'#932f0e', accentsoft:'#f7e8df', danger:'#a81e1e', price:'#8a5a00' },
      fontFamily: { serif: ['Georgia','Noto Serif Thai','TH Sarabun New','Times New Roman','serif'], sans: ['system-ui','Noto Sans Thai','sans-serif'] },
    },
  },
  plugins: [],
};
