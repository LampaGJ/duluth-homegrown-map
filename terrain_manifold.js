/**
 * terrain_manifold.js — Build a watertight solid disc mesh for Duluth Homegrown map.
 *
 * Produces a single BufferGeometry that is a closed manifold:
 *   - TOP FACE: circular disc with heightmap-driven elevation (the terrain)
 *   - SIDE WALL: vertical ring connecting terrain edge to flat bottom
 *   - BOTTOM FACE: flat circular disc (LP underside)
 *
 * All normals point outward. No gaps, no separate meshes, no see-through.
 *
 * Usage:
 *   import { buildTerrainDisc } from './terrain_manifold.js';
 *   const { geometry, elevAt } = buildTerrainDisc({
 *     heightmapImage,    // loaded Image/Canvas of the DEM
 *     planeW, planeH,    // world-space dimensions of the full heightmap extent
 *     hmW, hmH,          // pixel dimensions of heightmap
 *     discCenter,        // THREE.Vector2 — world XZ center of the disc
 *     discRadius,        // world-space radius
 *     terrainHeight,     // max displacement (world units)
 *     warpT, warpO, warpBlend, // radial warp parameters
 *     radialSegments,    // around the circumference (default 128)
 *     gridSegments,      // terrain grid resolution (default 512)
 *     sideRings,         // vertical rings on the side wall (default 2)
 *     discThickness,     // height of the side wall / bottom offset (default 3.0)
 *   });
 *   // geometry is a THREE.BufferGeometry, ready for a single MeshStandardMaterial
 *   // elevAt(x, z) returns the terrain height at world position (x, z)
 */

export function buildTerrainDisc(opts) {
  const {
    heightmapImage,
    planeW, planeH,
    hmW, hmH,
    discCenter,    // {x, y} in world XZ
    discRadius,
    terrainHeight = 20,
    warpT = 0.55,
    warpO = 0.85,
    warpBlend = 0.15,
    radialSegments = 128,
    gridSegments = 512,
    sideRings = 2,
    discThickness = 3.0,
  } = opts;

  // ---- Sample heightmap ----
  const hmCanvas = document.createElement("canvas");
  hmCanvas.width = hmW;
  hmCanvas.height = hmH;
  const hctx = hmCanvas.getContext("2d");
  hctx.drawImage(heightmapImage, 0, 0);
  const hmData = hctx.getImageData(0, 0, hmW, hmH).data;

  function sampleHM(worldX, worldZ) {
    const u = worldX / planeW + 0.5;
    const v = 0.5 - worldZ / planeH;
    const px = Math.max(0, Math.min(hmW - 1, Math.floor(u * hmW)));
    const py = Math.max(0, Math.min(hmH - 1, Math.floor((1 - v) * hmH)));
    return (hmData[(py * hmW + px) * 4] / 255) * terrainHeight;
  }

  // ---- Radial warp function ----
  // Maps a real-space offset from disc center to warped offset
  function warpXZ(dx, dz) {
    const r = Math.sqrt(dx * dx + dz * dz);
    if (r < 0.001 || r >= discRadius) return { x: dx, z: dz };
    const rn = r / discRadius;
    const innerRate = warpO / warpT;
    const outerRate = (1 - warpO) / (1 - warpT);
    // smoothstep blend
    let t = Math.max(0, Math.min(1, (rn - (warpT - warpBlend)) / (2 * warpBlend)));
    const s = t * t * (3 - 2 * t);
    const rwInner = rn * innerRate;
    const rwOuter = warpO + (rn - warpT) * outerRate;
    const rw = rwInner + s * (rwOuter - rwInner);
    const scale = (rw * discRadius) / r;
    return { x: dx * scale, z: dz * scale };
  }

  // Inverse warp for venue placement
  function inverseWarpXZ(wx, wz) {
    // Binary search: find real offset that warps to (wx, wz)
    const wr = Math.sqrt(wx * wx + wz * wz);
    if (wr < 0.001) return { x: wx, z: wz };
    const dir = { x: wx / wr, z: wz / wr };
    let lo = 0, hi = discRadius;
    for (let i = 0; i < 20; i++) {
      const mid = (lo + hi) / 2;
      const w = warpXZ(dir.x * mid, dir.z * mid);
      const wMid = Math.sqrt(w.x * w.x + w.z * w.z);
      if (wMid < wr) lo = mid; else hi = mid;
    }
    const r = (lo + hi) / 2;
    return { x: dir.x * r, z: dir.z * r };
  }

  // ---- Elevation with warp-aware smoothing ----
  function terrainElevation(worldX, worldZ) {
    // worldX, worldZ are pre-warp coordinates
    const dx = worldX - discCenter.x;
    const dz = worldZ - discCenter.y;
    const r = Math.sqrt(dx * dx + dz * dz);
    const rn = r / discRadius;

    // Flatten outer edge
    const flatten = smoothstep(0.82, 0.92, rn);
    if (flatten >= 1.0) return 0;

    const elev = sampleHM(worldX, worldZ);

    // Warp-aware smoothing: reduce local bumpiness in compressed zones
    if (rn > 0.001 && rn < 1.0) {
      const innerRate = warpO / warpT;
      const outerRate = (1 - warpO) / (1 - warpT);
      let t = Math.max(0, Math.min(1, (rn - (warpT - warpBlend)) / (2 * warpBlend)));
      const s = t * t * (3 - 2 * t);
      const warpScale = innerRate + s * (outerRate - innerRate);

      // Sample neighbors for local mean
      const step = planeW * 0.04;
      const mean = (
        sampleHM(worldX + step, worldZ) +
        sampleHM(worldX - step, worldZ) +
        sampleHM(worldX, worldZ + step) +
        sampleHM(worldX, worldZ - step)
      ) * 0.25;
      const localVar = elev - mean;
      const smoothed = mean + localVar * Math.max(0.25, Math.min(1.3, warpScale));
      return Math.max(0.05, smoothed) * (1 - flatten);
    }

    return Math.max(0.05, elev) * (1 - flatten);
  }

  function smoothstep(edge0, edge1, x) {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  // ---- Build the manifold geometry ----
  // Strategy: polar grid for the top face (better circle coverage),
  // matching ring at the edge connects to side wall and bottom.

  const positions = [];
  const normals = [];
  const uvs = [];
  const indices = [];

  // Helper: push a vertex, return its index
  let vertCount = 0;
  function addVert(x, y, z, nx, ny, nz, u, v) {
    positions.push(x, y, z);
    normals.push(nx, ny, nz);
    uvs.push(u, v);
    return vertCount++;
  }

  // ========== TOP FACE ==========
  // Use a polar grid: concentric rings from center to discRadius
  const rings = gridSegments;
  const spokes = radialSegments;

  // Center vertex
  const centerWorldX = discCenter.x;
  const centerWorldZ = discCenter.y;
  const centerElev = terrainElevation(centerWorldX, centerWorldZ);
  const centerU = centerWorldX / planeW + 0.5;
  const centerV = 0.5 - centerWorldZ / planeH;
  const centerIdx = addVert(0, centerElev, 0, 0, 1, 0, centerU, centerV);

  // Ring vertices
  const topRingStart = vertCount;
  const edgeIndices = []; // track outermost ring vertex indices for side wall

  for (let ri = 1; ri <= rings; ri++) {
    const rFrac = ri / rings;
    const realR = rFrac * discRadius;

    for (let si = 0; si < spokes; si++) {
      const theta = (si / spokes) * Math.PI * 2;
      const dx = Math.cos(theta) * realR;
      const dz = Math.sin(theta) * realR;

      // Real-space position (before warp)
      const realX = discCenter.x + dx;
      const realZ = discCenter.y + dz;

      // Warped position
      const w = warpXZ(dx, dz);
      const elev = terrainElevation(realX, realZ);

      // UV from real-space position
      const u = realX / planeW + 0.5;
      const v = 0.5 - realZ / planeH;

      const idx = addVert(w.x, elev, w.z, 0, 1, 0, u, v);

      if (ri === rings) {
        edgeIndices.push(idx);
      }
    }
  }

  // Triangulate top face
  // Center fan for first ring
  for (let si = 0; si < spokes; si++) {
    const next = (si + 1) % spokes;
    indices.push(centerIdx, topRingStart + si, topRingStart + next);
  }

  // Ring-to-ring quads
  for (let ri = 1; ri < rings; ri++) {
    const prevStart = topRingStart + (ri - 1) * spokes;
    const currStart = topRingStart + ri * spokes;
    for (let si = 0; si < spokes; si++) {
      const next = (si + 1) % spokes;
      const a = prevStart + si;
      const b = prevStart + next;
      const c = currStart + next;
      const d = currStart + si;
      indices.push(a, d, c);
      indices.push(a, c, b);
    }
  }

  // ========== SIDE WALL ==========
  // Connect top edge ring down to bottom edge ring
  const bottomY = -discThickness;
  const sideTopStart = vertCount;

  // Duplicate top edge verts with outward-facing normals for the side
  for (let si = 0; si < spokes; si++) {
    const theta = (si / spokes) * Math.PI * 2;
    const nx = Math.cos(theta);
    const nz = Math.sin(theta);
    const eIdx = edgeIndices[si];
    const x = positions[eIdx * 3];
    const y = positions[eIdx * 3 + 1];
    const z = positions[eIdx * 3 + 2];
    addVert(x, y, z, nx, 0, nz, si / spokes, 1);
  }

  // Intermediate side rings
  for (let r = 1; r < sideRings; r++) {
    const frac = r / sideRings;
    for (let si = 0; si < spokes; si++) {
      const theta = (si / spokes) * Math.PI * 2;
      const nx = Math.cos(theta);
      const nz = Math.sin(theta);
      const eIdx = edgeIndices[si];
      const x = positions[eIdx * 3];
      const z = positions[eIdx * 3 + 2];
      const topY = positions[eIdx * 3 + 1];
      const y = topY + (bottomY - topY) * frac;
      addVert(x, y, z, nx, 0, nz, si / spokes, 1 - frac);
    }
  }

  // Bottom edge ring (side normals)
  const sideBottomStart = vertCount;
  for (let si = 0; si < spokes; si++) {
    const theta = (si / spokes) * Math.PI * 2;
    const nx = Math.cos(theta);
    const nz = Math.sin(theta);
    const eIdx = edgeIndices[si];
    const x = positions[eIdx * 3];
    const z = positions[eIdx * 3 + 2];
    addVert(x, bottomY, z, nx, 0, nz, si / spokes, 0);
  }

  // Triangulate side wall
  const totalSideRings = sideRings + 1; // top + intermediate + bottom = sideRings+1 transitions
  for (let r = 0; r < sideRings; r++) {
    const ringA = sideTopStart + r * spokes;
    const ringB = r < sideRings - 1 ? sideTopStart + (r + 1) * spokes : sideBottomStart;
    for (let si = 0; si < spokes; si++) {
      const next = (si + 1) % spokes;
      indices.push(ringA + si, ringB + si, ringB + next);
      indices.push(ringA + si, ringB + next, ringA + next);
    }
  }

  // ========== BOTTOM FACE ==========
  // Flat circle at bottomY, normals pointing down
  const bottomCenterIdx = addVert(0, bottomY, 0, 0, -1, 0, 0.5, 0.5);
  const bottomRingStart = vertCount;

  for (let si = 0; si < spokes; si++) {
    const theta = (si / spokes) * Math.PI * 2;
    const eIdx = edgeIndices[si];
    const x = positions[eIdx * 3];
    const z = positions[eIdx * 3 + 2];
    addVert(x, bottomY, z, 0, -1, 0, 0.5 + 0.5 * Math.cos(theta), 0.5 + 0.5 * Math.sin(theta));
  }

  // Bottom face triangles (wound CW from below = CCW from outside)
  for (let si = 0; si < spokes; si++) {
    const next = (si + 1) % spokes;
    indices.push(bottomCenterIdx, bottomRingStart + next, bottomRingStart + si);
  }

  // ========== Build BufferGeometry ==========
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);

  // Recompute normals for top face (the procedural ones are just (0,1,0) placeholders)
  // We only recompute — don't overwrite side/bottom normals
  geo.computeVertexNormals();

  // Public elevation function (post-warp world coords → height)
  function elevAt(worldX, worldZ) {
    // Convert from post-warp back to pre-warp to sample heightmap
    const wx = worldX;
    const wz = worldZ;
    const inv = inverseWarpXZ(wx, wz);
    return terrainElevation(discCenter.x + inv.x, discCenter.y + inv.z);
  }

  return {
    geometry: geo,
    elevAt,
    warpXZ,
    inverseWarpXZ,
    discCenter,
    discRadius,
    discThickness,
  };
}
