"""Render the profile SVGs as looping GIFs. Requires Python Pillow, Node.js and sharp.
Run from the repository root: python scripts/animate-profile.py
Set NODE_PATH if sharp is installed outside the repository.
"""
from pathlib import Path
import json
import re
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES = 60
DURATION = 80

RENDER = r'''
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const config = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
  for (const theme of ['dark', 'light']) {
    const source = fs.readFileSync(path.join(config.root, 'assets', `profile-${theme}.svg`), 'utf8');
    const color = theme === 'dark' ? '#75D8C5' : '#17695C';
    for (let i = 0; i < config.frames; i++) {
      const phase = i / config.frames;
      const offset = -5 * Math.sin(phase * Math.PI * 2);
      // Move the complete die, including its number, as one object.
      let svg = source.replace(/  <g stroke="(#[A-Fa-f0-9]+)" stroke-width="1.7"/, `  <g transform="translate(0 ${offset})"><g stroke="$1" stroke-width="1.7"`)
        .replace(/(>20<\/text>)/, '$1</g>');
      // A short illuminated segment travels along each existing circuit.
      const paths = ['M780 92H844L876 124','M776 272H848L882 238','M1067 123L1100 90H1150','M1071 237L1104 270H1150'];
      const signals = paths.map((d, j) => {
        const progress = (phase + j * 0.25) % 1;
        const opacity = Math.sin(progress * Math.PI) * 0.85;
        return `<path d="${d}" pathLength="100" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-dasharray="9 191" stroke-dashoffset="${9 - progress * 109}" opacity="${opacity}"/>`;
      }).join('');
      svg = svg.replace('</svg>', signals + '</svg>');
      await sharp(Buffer.from(svg)).resize(1000, 300).flatten({background:theme === 'dark' ? '#0d1117' : '#ffffff'}).png().toFile(path.join(config.temp, `${theme}-${i}.png`));
    }
  }
})().catch(e => { console.error(e); process.exit(1); });
'''

with tempfile.TemporaryDirectory(prefix='cioscos-animation-') as temp:
    subprocess.run(['node', '-e', RENDER], input=json.dumps({'root': str(ROOT), 'temp': temp, 'frames': FRAMES}), text=True, check=True)
    for theme in ('dark', 'light'):
        images = [Image.open(Path(temp) / f'{theme}-{i}.png').convert('RGB') for i in range(FRAMES)]
        # One shared palette prevents color flicker between frames.
        palette = images[0].quantize(colors=240)
        # Reserve the original accent and text colors instead of letting the
        # large background dominate the quantizer's color budget.
        colors = list(dict.fromkeys(re.findall(r'#[0-9A-Fa-f]{6}', (ROOT / 'assets' / f'profile-{theme}.svg').read_text(encoding='utf-8-sig'))))
        reserved = [int(color[i:i + 2], 16) for color in colors[:16] for i in (1, 3, 5)]
        entries = palette.getpalette()[:720] + reserved
        palette.putpalette(entries + [0] * (768 - len(entries)))
        frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
        output = ROOT / 'assets' / f'profile-{theme}.gif'
        frames[0].save(output, save_all=True, append_images=frames[1:], duration=DURATION, loop=0, optimize=True, disposal=1)
        with Image.open(output) as result:
            assert result.n_frames == FRAMES
            assert result.size == (1000, 300)
            assert result.info['loop'] == 0
        print(f'{output.name}: {FRAMES} frames, {FRAMES * DURATION / 1000:.1f}s loop, {output.stat().st_size:,} bytes')
