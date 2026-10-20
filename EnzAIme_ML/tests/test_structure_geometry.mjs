import assert from 'node:assert/strict'
import { smoothBackbone } from '../frontend/src/structureGeometry.js'

const coordinates = [{ xyz: [0, 0, 0] }, { xyz: [3, 1, 0] }, { xyz: [6, 0, 0] }, { xyz: [30, 0, 0] }]
const original = JSON.stringify(coordinates)
const smooth = smoothBackbone(coordinates)
assert.equal(smooth.length, 12)
assert.deepEqual(smooth[0].from, coordinates[0].xyz)
assert.deepEqual(smooth[5].to, coordinates[1].xyz)
assert.deepEqual(smooth[11].to, coordinates[2].xyz)
assert.ok(smooth.every((segment) => [...segment.from, ...segment.to].every(Number.isFinite)))
assert.equal(smoothBackbone(coordinates, false).length, 2)
assert.equal(smoothBackbone([]).length, 0)
assert.equal(smoothBackbone([coordinates[0]]).length, 0)
assert.equal(JSON.stringify(coordinates), original)
console.log('Geometry checks passed: preserved coordinates, exact residue endpoints, and no bridge across gaps.')
