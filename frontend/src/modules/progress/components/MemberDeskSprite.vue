<script setup lang="ts">
import { computed } from 'vue'
import { clothingHex, memberPixelUri } from '../pixel-avatar'

const props = defineProps<{
  seed: string
  name: string
  color?: string | null
  busy: boolean
}>()

const portrait = computed(() => memberPixelUri(props.seed, props.color))
const accent = computed(() => `#${clothingHex(props.color)}`)
const floorId = computed(() => `desk-floor-${props.seed.replace(/[^a-zA-Z0-9_-]/g, '')}`)
</script>

<template>
  <div class="desk-scene" :class="busy ? 'desk-scene--busy' : 'desk-scene--idle'">
    <svg class="desk-scene__room" viewBox="0 0 128 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <pattern :id="floorId" width="8" height="8" patternUnits="userSpaceOnUse">
          <rect width="8" height="8" fill="#12202e" />
          <rect width="4" height="4" fill="#162636" />
          <rect x="4" y="4" width="4" height="4" fill="#162636" />
        </pattern>
      </defs>
      <rect width="128" height="46" fill="#0c1924" />
      <rect y="6" width="128" height="2" fill="#101e2a" />
      <rect y="16" width="128" height="2" fill="#101e2a" />
      <rect y="26" width="128" height="2" fill="#101e2a" />
      <rect y="36" width="128" height="10" fill="#152433" />
      <rect x="4" y="10" width="14" height="16" fill="#1a3142" />
      <rect x="5" y="11" width="12" height="10" fill="#243c4e" />
      <rect x="6" y="12" width="3" height="3" fill="#36d9e9" opacity=".4" />
      <rect x="11" y="14" width="4" height="2" fill="#5ce0ae" opacity=".28" />
      <rect x="7" y="18" width="8" height="1" fill="#0b1620" opacity=".4" />
      <rect x="86" y="5" width="38" height="26" fill="#2b4556" />
      <rect x="88" y="7" width="34" height="22" fill="#071821" />
      <rect x="104" y="7" width="2" height="22" fill="#2b4556" />
      <rect x="88" y="17" width="34" height="2" fill="#2b4556" />
      <rect x="91" y="10" width="3" height="5" fill="#1a3a4c" />
      <rect x="96" y="13" width="5" height="8" fill="#163445" />
      <rect x="108" y="9" width="4" height="7" fill="#1c4258" />
      <rect x="114" y="12" width="3" height="10" fill="#143040" />
      <rect x="93" y="12" width="2" height="2" fill="#36d9e9" opacity=".7" />
      <rect x="99" y="16" width="2" height="2" fill="#fcd34d" opacity=".55" />
      <rect x="110" y="11" width="2" height="2" fill="#5ce0ae" opacity=".5" />
      <rect x="116" y="18" width="1" height="1" fill="#d7e2eb" opacity=".45" />
      <rect x="88" y="29" width="34" height="3" fill="#3a2718" />
      <rect x="114" y="23" width="6" height="7" fill="#1f6b46" />
      <rect x="115" y="21" width="4" height="3" fill="#2f8a5c" />
      <rect x="117" y="20" width="2" height="2" fill="#3fa86e" />
      <rect y="46" width="128" height="34" :fill="`url(#${floorId})`" />
      <rect y="46" width="128" height="3" fill="#1b3344" />
      <rect x="44" y="32" width="40" height="22" fill="#1a2d3c" />
      <rect x="46" y="34" width="36" height="4" fill="#274155" />
      <rect x="48" y="38" width="32" height="16" fill="#152633" />
      <rect x="47" y="38" width="3" height="12" fill="#203848" />
      <rect x="78" y="38" width="3" height="12" fill="#203848" />
      <rect x="62" y="0" width="2" height="8" fill="#334656" />
      <rect x="57" y="8" width="12" height="4" fill="#c9a227" />
      <rect x="59" y="12" width="8" height="2" fill="#fcd34d" opacity=".85" />
    </svg>
    <img class="desk-scene__person" :src="portrait" :alt="`${name} 的像素形象`" width="80" height="80" />
    <svg class="desk-scene__props" viewBox="0 0 128 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <g v-if="!busy">
        <rect x="74" y="38" width="8" height="14" fill="#1a1f24" />
        <rect x="75" y="39" width="6" height="11" :fill="accent" class="desk-scene__screen" />
        <rect x="76" y="40" width="4" height="1" fill="#071019" opacity=".32" />
        <rect x="76" y="43" width="3" height="1" fill="#071019" opacity=".22" />
        <rect x="77" y="38" width="2" height="1" fill="#2a3340" />
      </g>
    </svg>
    <svg class="desk-scene__desk" viewBox="0 0 128 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="12" y="63" width="104" height="4" fill="#0a1218" opacity=".5" />
      <rect x="10" y="52" width="108" height="11" fill="#4a3220" />
      <rect x="10" y="52" width="108" height="2" fill="#7a5634" />
      <rect x="10" y="54" width="108" height="1" fill="#5c3e26" />
      <rect x="10" y="61" width="108" height="3" fill="#2e1d12" />
      <rect x="16" y="64" width="5" height="12" fill="#24160e" />
      <rect x="107" y="64" width="5" height="12" fill="#24160e" />
      <rect x="18" y="49" width="8" height="5" fill="#3e2a1c" />
      <rect x="19" y="46" width="6" height="5" fill="#c45c38" />
      <rect x="20" y="47" width="4" height="2" fill="#ead9c4" />
      <rect x="21" y="46" width="2" height="1" fill="#ead9c4" opacity=".7" />
      <rect x="102" y="48" width="10" height="5" fill="#2a1c12" />
      <rect x="103" y="47" width="8" height="2" fill="#5ce0ae" />
      <rect x="104" y="45" width="6" height="3" fill="#36d9e9" />
      <g v-if="busy">
        <rect x="45" y="48" width="38" height="6" fill="#1c242c" />
        <rect x="47" y="32" width="34" height="18" fill="#11181f" />
        <rect x="49" y="34" width="30" height="14" :fill="accent" class="desk-scene__screen" />
        <rect x="51" y="36" width="12" height="1" fill="#071019" opacity=".35" />
        <rect x="51" y="39" width="18" height="1" fill="#071019" opacity=".28" />
        <rect x="51" y="42" width="9" height="1" fill="#071019" opacity=".22" />
        <rect x="62" y="50" width="4" height="2" fill="#2a3340" />
        <rect x="48" y="54" width="20" height="3" fill="#24303a" />
        <rect x="50" y="55" width="2" height="1" fill="#5a6a76" />
        <rect x="54" y="55" width="2" height="1" fill="#5a6a76" />
        <rect x="58" y="55" width="2" height="1" fill="#5a6a76" />
        <rect x="88" y="50" width="12" height="3" fill="#d7e2eb" />
        <rect x="90" y="49" width="8" height="1" fill="#9bafc0" />
      </g>
      <g v-else>
        <rect x="44" y="50" width="18" height="3" fill="#d7e2eb" />
        <rect x="46" y="49" width="12" height="1" fill="#9bafc0" />
      </g>
    </svg>
    <span class="desk-scene__lamp" aria-hidden="true" />
    <p class="desk-scene__caption">{{ busy ? '对着笔记本' : '拿着手机刷' }}</p>
  </div>
</template>

<style scoped>
.desk-scene {
  position: relative;
  height: 172px;
  overflow: hidden;
  border: 1px solid #2a4154;
  border-radius: 10px;
  background: #0c1924;
  box-shadow: inset 0 -20px 32px rgb(0 0 0 / .32);
}
.desk-scene__room,
.desk-scene__props,
.desk-scene__desk {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
  shape-rendering: crispEdges;
}
.desk-scene__props { z-index: 2; }
.desk-scene__desk { z-index: 3; }
.desk-scene__person {
  position: absolute;
  z-index: 1;
  left: 50%;
  bottom: 42px;
  width: 92px;
  height: 92px;
  translate: -50% 0;
  image-rendering: pixelated;
  filter: drop-shadow(0 2px 0 rgb(0 0 0 / .4));
}
.desk-scene--idle .desk-scene__person { left: 47%; }
.desk-scene__lamp {
  position: absolute;
  z-index: 4;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 48% 38% at 50% 18%, rgb(252 211 77 / .16), transparent 58%),
    radial-gradient(ellipse 42% 34% at 50% 58%, rgb(54 217 233 / .08), transparent 70%);
}
.desk-scene--idle .desk-scene__lamp {
  background:
    radial-gradient(ellipse 36% 30% at 50% 16%, rgb(252 211 77 / .1), transparent 56%),
    radial-gradient(ellipse 26% 28% at 60% 50%, rgb(252 211 77 / .12), transparent 68%);
}
.desk-scene__caption {
  position: absolute;
  z-index: 5;
  left: 8px;
  bottom: 7px;
  border: 1px solid rgb(54 217 233 / .2);
  border-radius: 99px;
  background: rgb(7 16 25 / .78);
  padding: 3px 8px;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: .04em;
  color: #d7e2eb;
}
.desk-scene__screen { animation: desk-glow 1.8s steps(2, end) infinite; }
@keyframes desk-glow {
  50% { opacity: .62; }
}
@media (prefers-reduced-motion: reduce) {
  .desk-scene__screen { animation: none; }
}
</style>
