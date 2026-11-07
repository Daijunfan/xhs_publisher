import {
  C as lt,
  V as E,
  M as D,
  T as M,
  Q as tt,
  S as et,
  a as g,
  R as ct,
  P as dt,
  b as j,
  W as pt,
  c as nt,
  d as mt,
  e as ut,
  f as _t,
  g as ft,
  h as bt,
  A as yt,
  D as st,
  i as gt,
  j as Et,
  k as Pt,
  l as L,
  m as wt,
  n as Mt,
  o as Dt,
} from "./globe-C4p2zDM5.js";
import { c as it, i as x, e as St } from "./index-19fec4aed5d7.js";
const ot = { type: "change" },
  W = { type: "start" },
  ht = { type: "end" },
  O = new ct(),
  at = new dt(),
  Tt = Math.cos(70 * j.DEG2RAD),
  d = new E(),
  u = 2 * Math.PI,
  r = {
    NONE: -1,
    ROTATE: 0,
    DOLLY: 1,
    PAN: 2,
    TOUCH_ROTATE: 3,
    TOUCH_PAN: 4,
    TOUCH_DOLLY_PAN: 5,
    TOUCH_DOLLY_ROTATE: 6,
  },
  H = 1e-6;
class xt extends lt {
  constructor(t, e = null) {
    (super(t, e),
      (this.state = r.NONE),
      (this.target = new E()),
      (this.cursor = new E()),
      (this.minDistance = 0),
      (this.maxDistance = 1 / 0),
      (this.minZoom = 0),
      (this.maxZoom = 1 / 0),
      (this.minTargetRadius = 0),
      (this.maxTargetRadius = 1 / 0),
      (this.minPolarAngle = 0),
      (this.maxPolarAngle = Math.PI),
      (this.minAzimuthAngle = -1 / 0),
      (this.maxAzimuthAngle = 1 / 0),
      (this.enableDamping = !1),
      (this.dampingFactor = 0.05),
      (this.enableZoom = !0),
      (this.zoomSpeed = 1),
      (this.enableRotate = !0),
      (this.rotateSpeed = 1),
      (this.keyRotateSpeed = 1),
      (this.enablePan = !0),
      (this.panSpeed = 1),
      (this.screenSpacePanning = !0),
      (this.keyPanSpeed = 7),
      (this.zoomToCursor = !1),
      (this.autoRotate = !1),
      (this.autoRotateSpeed = 2),
      (this.keys = {
        LEFT: "ArrowLeft",
        UP: "ArrowUp",
        RIGHT: "ArrowRight",
        BOTTOM: "ArrowDown",
      }),
      (this.mouseButtons = { LEFT: D.ROTATE, MIDDLE: D.DOLLY, RIGHT: D.PAN }),
      (this.touches = { ONE: M.ROTATE, TWO: M.DOLLY_PAN }),
      (this.target0 = this.target.clone()),
      (this.position0 = this.object.position.clone()),
      (this.zoom0 = this.object.zoom),
      (this._domElementKeyEvents = null),
      (this._lastPosition = new E()),
      (this._lastQuaternion = new tt()),
      (this._lastTargetPosition = new E()),
      (this._quat = new tt().setFromUnitVectors(t.up, new E(0, 1, 0))),
      (this._quatInverse = this._quat.clone().invert()),
      (this._spherical = new et()),
      (this._sphericalDelta = new et()),
      (this._scale = 1),
      (this._panOffset = new E()),
      (this._rotateStart = new g()),
      (this._rotateEnd = new g()),
      (this._rotateDelta = new g()),
      (this._panStart = new g()),
      (this._panEnd = new g()),
      (this._panDelta = new g()),
      (this._dollyStart = new g()),
      (this._dollyEnd = new g()),
      (this._dollyDelta = new g()),
      (this._dollyDirection = new E()),
      (this._mouse = new g()),
      (this._performCursorZoom = !1),
      (this._pointers = []),
      (this._pointerPositions = {}),
      (this._controlActive = !1),
      (this._onPointerMove = At.bind(this)),
      (this._onPointerDown = Rt.bind(this)),
      (this._onPointerUp = vt.bind(this)),
      (this._onContextMenu = It.bind(this)),
      (this._onMouseWheel = Ot.bind(this)),
      (this._onKeyDown = jt.bind(this)),
      (this._onTouchStart = kt.bind(this)),
      (this._onTouchMove = Nt.bind(this)),
      (this._onMouseDown = Ct.bind(this)),
      (this._onMouseMove = Lt.bind(this)),
      (this._interceptControlDown = zt.bind(this)),
      (this._interceptControlUp = Yt.bind(this)),
      this.domElement !== null && this.connect(this.domElement),
      this.update());
  }
  connect(t) {
    (super.connect(t),
      this.domElement.addEventListener("pointerdown", this._onPointerDown),
      this.domElement.addEventListener("pointercancel", this._onPointerUp),
      this.domElement.addEventListener("contextmenu", this._onContextMenu),
      this.domElement.addEventListener("wheel", this._onMouseWheel, {
        passive: !1,
      }),
      this.domElement
        .getRootNode()
        .addEventListener("keydown", this._interceptControlDown, {
          passive: !0,
          capture: !0,
        }),
      (this.domElement.style.touchAction = "none"));
  }
  disconnect() {
    (this.domElement.removeEventListener("pointerdown", this._onPointerDown),
      this.domElement.removeEventListener("pointermove", this._onPointerMove),
      this.domElement.removeEventListener("pointerup", this._onPointerUp),
      this.domElement.removeEventListener("pointercancel", this._onPointerUp),
      this.domElement.removeEventListener("wheel", this._onMouseWheel),
      this.domElement.removeEventListener("contextmenu", this._onContextMenu),
      this.stopListenToKeyEvents(),
      this.domElement
        .getRootNode()
        .removeEventListener("keydown", this._interceptControlDown, {
          capture: !0,
        }),
      (this.domElement.style.touchAction = "auto"));
  }
  dispose() {
    this.disconnect();
  }
  getPolarAngle() {
    return this._spherical.phi;
  }
  getAzimuthalAngle() {
    return this._spherical.theta;
  }
  getDistance() {
    return this.object.position.distanceTo(this.target);
  }
  listenToKeyEvents(t) {
    (t.addEventListener("keydown", this._onKeyDown),
      (this._domElementKeyEvents = t));
  }
  stopListenToKeyEvents() {
    this._domElementKeyEvents !== null &&
      (this._domElementKeyEvents.removeEventListener(
        "keydown",
        this._onKeyDown,
      ),
      (this._domElementKeyEvents = null));
  }
  saveState() {
    (this.target0.copy(this.target),
      this.position0.copy(this.object.position),
      (this.zoom0 = this.object.zoom));
  }
  reset() {
    (this.target.copy(this.target0),
      this.object.position.copy(this.position0),
      (this.object.zoom = this.zoom0),
      this.object.updateProjectionMatrix(),
      this.dispatchEvent(ot),
      this.update(),
      (this.state = r.NONE));
  }
  update(t = null) {
    const e = this.object.position;
    (d.copy(e).sub(this.target),
      d.applyQuaternion(this._quat),
      this._spherical.setFromVector3(d),
      this.autoRotate &&
        this.state === r.NONE &&
        this._rotateLeft(this._getAutoRotationAngle(t)),
      this.enableDamping
        ? ((this._spherical.theta +=
            this._sphericalDelta.theta * this.dampingFactor),
          (this._spherical.phi +=
            this._sphericalDelta.phi * this.dampingFactor))
        : ((this._spherical.theta += this._sphericalDelta.theta),
          (this._spherical.phi += this._sphericalDelta.phi)));
    let s = this.minAzimuthAngle,
      o = this.maxAzimuthAngle;
    (isFinite(s) &&
      isFinite(o) &&
      (s < -Math.PI ? (s += u) : s > Math.PI && (s -= u),
      o < -Math.PI ? (o += u) : o > Math.PI && (o -= u),
      s <= o
        ? (this._spherical.theta = Math.max(
            s,
            Math.min(o, this._spherical.theta),
          ))
        : (this._spherical.theta =
            this._spherical.theta > (s + o) / 2
              ? Math.max(s, this._spherical.theta)
              : Math.min(o, this._spherical.theta))),
      (this._spherical.phi = Math.max(
        this.minPolarAngle,
        Math.min(this.maxPolarAngle, this._spherical.phi),
      )),
      this._spherical.makeSafe(),
      this.enableDamping === !0
        ? this.target.addScaledVector(this._panOffset, this.dampingFactor)
        : this.target.add(this._panOffset),
      this.target.sub(this.cursor),
      this.target.clampLength(this.minTargetRadius, this.maxTargetRadius),
      this.target.add(this.cursor));
    let h = !1;
    if (
      (this.zoomToCursor && this._performCursorZoom) ||
      this.object.isOrthographicCamera
    )
      this._spherical.radius = this._clampDistance(this._spherical.radius);
    else {
      const l = this._spherical.radius;
      ((this._spherical.radius = this._clampDistance(
        this._spherical.radius * this._scale,
      )),
        (h = l != this._spherical.radius));
    }
    if (
      (d.setFromSpherical(this._spherical),
      d.applyQuaternion(this._quatInverse),
      e.copy(this.target).add(d),
      this.object.lookAt(this.target),
      this.enableDamping === !0
        ? ((this._sphericalDelta.theta *= 1 - this.dampingFactor),
          (this._sphericalDelta.phi *= 1 - this.dampingFactor),
          this._panOffset.multiplyScalar(1 - this.dampingFactor))
        : (this._sphericalDelta.set(0, 0, 0), this._panOffset.set(0, 0, 0)),
      this.zoomToCursor && this._performCursorZoom)
    ) {
      let l = null;
      if (this.object.isPerspectiveCamera) {
        const m = d.length();
        l = this._clampDistance(m * this._scale);
        const f = m - l;
        (this.object.position.addScaledVector(this._dollyDirection, f),
          this.object.updateMatrixWorld(),
          (h = !!f));
      } else if (this.object.isOrthographicCamera) {
        const m = new E(this._mouse.x, this._mouse.y, 0);
        m.unproject(this.object);
        const f = this.object.zoom;
        ((this.object.zoom = Math.max(
          this.minZoom,
          Math.min(this.maxZoom, this.object.zoom / this._scale),
        )),
          this.object.updateProjectionMatrix(),
          (h = f !== this.object.zoom));
        const w = new E(this._mouse.x, this._mouse.y, 0);
        (w.unproject(this.object),
          this.object.position.sub(w).add(m),
          this.object.updateMatrixWorld(),
          (l = d.length()));
      } else
        (console.warn(
          "WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled.",
        ),
          (this.zoomToCursor = !1));
      l !== null &&
        (this.screenSpacePanning
          ? this.target
              .set(0, 0, -1)
              .transformDirection(this.object.matrix)
              .multiplyScalar(l)
              .add(this.object.position)
          : (O.origin.copy(this.object.position),
            O.direction.set(0, 0, -1).transformDirection(this.object.matrix),
            Math.abs(this.object.up.dot(O.direction)) < Tt
              ? this.object.lookAt(this.target)
              : (at.setFromNormalAndCoplanarPoint(this.object.up, this.target),
                O.intersectPlane(at, this.target))));
    } else if (this.object.isOrthographicCamera) {
      const l = this.object.zoom;
      ((this.object.zoom = Math.max(
        this.minZoom,
        Math.min(this.maxZoom, this.object.zoom / this._scale),
      )),
        l !== this.object.zoom &&
          (this.object.updateProjectionMatrix(), (h = !0)));
    }
    return (
      (this._scale = 1),
      (this._performCursorZoom = !1),
      h ||
      this._lastPosition.distanceToSquared(this.object.position) > H ||
      8 * (1 - this._lastQuaternion.dot(this.object.quaternion)) > H ||
      this._lastTargetPosition.distanceToSquared(this.target) > H
        ? (this.dispatchEvent(ot),
          this._lastPosition.copy(this.object.position),
          this._lastQuaternion.copy(this.object.quaternion),
          this._lastTargetPosition.copy(this.target),
          !0)
        : !1
    );
  }
  _getAutoRotationAngle(t) {
    return t !== null
      ? (u / 60) * this.autoRotateSpeed * t
      : (u / 60 / 60) * this.autoRotateSpeed;
  }
  _getZoomScale(t) {
    const e = Math.abs(t * 0.01);
    return Math.pow(0.95, this.zoomSpeed * e);
  }
  _rotateLeft(t) {
    this._sphericalDelta.theta -= t;
  }
  _rotateUp(t) {
    this._sphericalDelta.phi -= t;
  }
  _panLeft(t, e) {
    (d.setFromMatrixColumn(e, 0), d.multiplyScalar(-t), this._panOffset.add(d));
  }
  _panUp(t, e) {
    (this.screenSpacePanning === !0
      ? d.setFromMatrixColumn(e, 1)
      : (d.setFromMatrixColumn(e, 0), d.crossVectors(this.object.up, d)),
      d.multiplyScalar(t),
      this._panOffset.add(d));
  }
  _pan(t, e) {
    const s = this.domElement;
    if (this.object.isPerspectiveCamera) {
      const o = this.object.position;
      d.copy(o).sub(this.target);
      let h = d.length();
      ((h *= Math.tan(((this.object.fov / 2) * Math.PI) / 180)),
        this._panLeft((2 * t * h) / s.clientHeight, this.object.matrix),
        this._panUp((2 * e * h) / s.clientHeight, this.object.matrix));
    } else
      this.object.isOrthographicCamera
        ? (this._panLeft(
            (t * (this.object.right - this.object.left)) /
              this.object.zoom /
              s.clientWidth,
            this.object.matrix,
          ),
          this._panUp(
            (e * (this.object.top - this.object.bottom)) /
              this.object.zoom /
              s.clientHeight,
            this.object.matrix,
          ))
        : (console.warn(
            "WARNING: OrbitControls.js encountered an unknown camera type - pan disabled.",
          ),
          (this.enablePan = !1));
  }
  _dollyOut(t) {
    this.object.isPerspectiveCamera || this.object.isOrthographicCamera
      ? (this._scale /= t)
      : (console.warn(
          "WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.",
        ),
        (this.enableZoom = !1));
  }
  _dollyIn(t) {
    this.object.isPerspectiveCamera || this.object.isOrthographicCamera
      ? (this._scale *= t)
      : (console.warn(
          "WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.",
        ),
        (this.enableZoom = !1));
  }
  _updateZoomParameters(t, e) {
    if (!this.zoomToCursor) return;
    this._performCursorZoom = !0;
    const s = this.domElement.getBoundingClientRect(),
      o = t - s.left,
      h = e - s.top,
      l = s.width,
      m = s.height;
    ((this._mouse.x = (o / l) * 2 - 1),
      (this._mouse.y = -(h / m) * 2 + 1),
      this._dollyDirection
        .set(this._mouse.x, this._mouse.y, 1)
        .unproject(this.object)
        .sub(this.object.position)
        .normalize());
  }
  _clampDistance(t) {
    return Math.max(this.minDistance, Math.min(this.maxDistance, t));
  }
  _handleMouseDownRotate(t) {
    this._rotateStart.set(t.clientX, t.clientY);
  }
  _handleMouseDownDolly(t) {
    (this._updateZoomParameters(t.clientX, t.clientX),
      this._dollyStart.set(t.clientX, t.clientY));
  }
  _handleMouseDownPan(t) {
    this._panStart.set(t.clientX, t.clientY);
  }
  _handleMouseMoveRotate(t) {
    (this._rotateEnd.set(t.clientX, t.clientY),
      this._rotateDelta
        .subVectors(this._rotateEnd, this._rotateStart)
        .multiplyScalar(this.rotateSpeed));
    const e = this.domElement;
    (this._rotateLeft((u * this._rotateDelta.x) / e.clientHeight),
      this._rotateUp((u * this._rotateDelta.y) / e.clientHeight),
      this._rotateStart.copy(this._rotateEnd),
      this.update());
  }
  _handleMouseMoveDolly(t) {
    (this._dollyEnd.set(t.clientX, t.clientY),
      this._dollyDelta.subVectors(this._dollyEnd, this._dollyStart),
      this._dollyDelta.y > 0
        ? this._dollyOut(this._getZoomScale(this._dollyDelta.y))
        : this._dollyDelta.y < 0 &&
          this._dollyIn(this._getZoomScale(this._dollyDelta.y)),
      this._dollyStart.copy(this._dollyEnd),
      this.update());
  }
  _handleMouseMovePan(t) {
    (this._panEnd.set(t.clientX, t.clientY),
      this._panDelta
        .subVectors(this._panEnd, this._panStart)
        .multiplyScalar(this.panSpeed),
      this._pan(this._panDelta.x, this._panDelta.y),
      this._panStart.copy(this._panEnd),
      this.update());
  }
  _handleMouseWheel(t) {
    (this._updateZoomParameters(t.clientX, t.clientY),
      t.deltaY < 0
        ? this._dollyIn(this._getZoomScale(t.deltaY))
        : t.deltaY > 0 && this._dollyOut(this._getZoomScale(t.deltaY)),
      this.update());
  }
  _handleKeyDown(t) {
    let e = !1;
    switch (t.code) {
      case this.keys.UP:
        (t.ctrlKey || t.metaKey || t.shiftKey
          ? this.enableRotate &&
            this._rotateUp(
              (u * this.keyRotateSpeed) / this.domElement.clientHeight,
            )
          : this.enablePan && this._pan(0, this.keyPanSpeed),
          (e = !0));
        break;
      case this.keys.BOTTOM:
        (t.ctrlKey || t.metaKey || t.shiftKey
          ? this.enableRotate &&
            this._rotateUp(
              (-u * this.keyRotateSpeed) / this.domElement.clientHeight,
            )
          : this.enablePan && this._pan(0, -this.keyPanSpeed),
          (e = !0));
        break;
      case this.keys.LEFT:
        (t.ctrlKey || t.metaKey || t.shiftKey
          ? this.enableRotate &&
            this._rotateLeft(
              (u * this.keyRotateSpeed) / this.domElement.clientHeight,
            )
          : this.enablePan && this._pan(this.keyPanSpeed, 0),
          (e = !0));
        break;
      case this.keys.RIGHT:
        (t.ctrlKey || t.metaKey || t.shiftKey
          ? this.enableRotate &&
            this._rotateLeft(
              (-u * this.keyRotateSpeed) / this.domElement.clientHeight,
            )
          : this.enablePan && this._pan(-this.keyPanSpeed, 0),
          (e = !0));
        break;
    }
    e && (t.preventDefault(), this.update());
  }
  _handleTouchStartRotate(t) {
    if (this._pointers.length === 1) this._rotateStart.set(t.pageX, t.pageY);
    else {
      const e = this._getSecondPointerPosition(t),
        s = 0.5 * (t.pageX + e.x),
        o = 0.5 * (t.pageY + e.y);
      this._rotateStart.set(s, o);
    }
  }
  _handleTouchStartPan(t) {
    if (this._pointers.length === 1) this._panStart.set(t.pageX, t.pageY);
    else {
      const e = this._getSecondPointerPosition(t),
        s = 0.5 * (t.pageX + e.x),
        o = 0.5 * (t.pageY + e.y);
      this._panStart.set(s, o);
    }
  }
  _handleTouchStartDolly(t) {
    const e = this._getSecondPointerPosition(t),
      s = t.pageX - e.x,
      o = t.pageY - e.y,
      h = Math.sqrt(s * s + o * o);
    this._dollyStart.set(0, h);
  }
  _handleTouchStartDollyPan(t) {
    (this.enableZoom && this._handleTouchStartDolly(t),
      this.enablePan && this._handleTouchStartPan(t));
  }
  _handleTouchStartDollyRotate(t) {
    (this.enableZoom && this._handleTouchStartDolly(t),
      this.enableRotate && this._handleTouchStartRotate(t));
  }
  _handleTouchMoveRotate(t) {
    if (this._pointers.length == 1) this._rotateEnd.set(t.pageX, t.pageY);
    else {
      const s = this._getSecondPointerPosition(t),
        o = 0.5 * (t.pageX + s.x),
        h = 0.5 * (t.pageY + s.y);
      this._rotateEnd.set(o, h);
    }
    this._rotateDelta
      .subVectors(this._rotateEnd, this._rotateStart)
      .multiplyScalar(this.rotateSpeed);
    const e = this.domElement;
    (this._rotateLeft((u * this._rotateDelta.x) / e.clientHeight),
      this._rotateUp((u * this._rotateDelta.y) / e.clientHeight),
      this._rotateStart.copy(this._rotateEnd));
  }
  _handleTouchMovePan(t) {
    if (this._pointers.length === 1) this._panEnd.set(t.pageX, t.pageY);
    else {
      const e = this._getSecondPointerPosition(t),
        s = 0.5 * (t.pageX + e.x),
        o = 0.5 * (t.pageY + e.y);
      this._panEnd.set(s, o);
    }
    (this._panDelta
      .subVectors(this._panEnd, this._panStart)
      .multiplyScalar(this.panSpeed),
      this._pan(this._panDelta.x, this._panDelta.y),
      this._panStart.copy(this._panEnd));
  }
  _handleTouchMoveDolly(t) {
    const e = this._getSecondPointerPosition(t),
      s = t.pageX - e.x,
      o = t.pageY - e.y,
      h = Math.sqrt(s * s + o * o);
    (this._dollyEnd.set(0, h),
      this._dollyDelta.set(
        0,
        Math.pow(this._dollyEnd.y / this._dollyStart.y, this.zoomSpeed),
      ),
      this._dollyOut(this._dollyDelta.y),
      this._dollyStart.copy(this._dollyEnd));
    const l = (t.pageX + e.x) * 0.5,
      m = (t.pageY + e.y) * 0.5;
    this._updateZoomParameters(l, m);
  }
  _handleTouchMoveDollyPan(t) {
    (this.enableZoom && this._handleTouchMoveDolly(t),
      this.enablePan && this._handleTouchMovePan(t));
  }
  _handleTouchMoveDollyRotate(t) {
    (this.enableZoom && this._handleTouchMoveDolly(t),
      this.enableRotate && this._handleTouchMoveRotate(t));
  }
  _addPointer(t) {
    this._pointers.push(t.pointerId);
  }
  _removePointer(t) {
    delete this._pointerPositions[t.pointerId];
    for (let e = 0; e < this._pointers.length; e++)
      if (this._pointers[e] == t.pointerId) {
        this._pointers.splice(e, 1);
        return;
      }
  }
  _isTrackingPointer(t) {
    for (let e = 0; e < this._pointers.length; e++)
      if (this._pointers[e] == t.pointerId) return !0;
    return !1;
  }
  _trackPointer(t) {
    let e = this._pointerPositions[t.pointerId];
    (e === void 0 && ((e = new g()), (this._pointerPositions[t.pointerId] = e)),
      e.set(t.pageX, t.pageY));
  }
  _getSecondPointerPosition(t) {
    const e =
      t.pointerId === this._pointers[0] ? this._pointers[1] : this._pointers[0];
    return this._pointerPositions[e];
  }
  _customWheelEvent(t) {
    const e = t.deltaMode,
      s = { clientX: t.clientX, clientY: t.clientY, deltaY: t.deltaY };
    switch (e) {
      case 1:
        s.deltaY *= 16;
        break;
      case 2:
        s.deltaY *= 100;
        break;
    }
    return (t.ctrlKey && !this._controlActive && (s.deltaY *= 10), s);
  }
}
function Rt(i) {
  this.enabled !== !1 &&
    (this._pointers.length === 0 &&
      (this.domElement.setPointerCapture(i.pointerId),
      this.domElement.addEventListener("pointermove", this._onPointerMove),
      this.domElement.addEventListener("pointerup", this._onPointerUp)),
    !this._isTrackingPointer(i) &&
      (this._addPointer(i),
      i.pointerType === "touch"
        ? this._onTouchStart(i)
        : this._onMouseDown(i)));
}
function At(i) {
  this.enabled !== !1 &&
    (i.pointerType === "touch" ? this._onTouchMove(i) : this._onMouseMove(i));
}
function vt(i) {
  switch ((this._removePointer(i), this._pointers.length)) {
    case 0:
      (this.domElement.releasePointerCapture(i.pointerId),
        this.domElement.removeEventListener("pointermove", this._onPointerMove),
        this.domElement.removeEventListener("pointerup", this._onPointerUp),
        this.dispatchEvent(ht),
        (this.state = r.NONE));
      break;
    case 1:
      const t = this._pointers[0],
        e = this._pointerPositions[t];
      this._onTouchStart({ pointerId: t, pageX: e.x, pageY: e.y });
      break;
  }
}
function Ct(i) {
  let t;
  switch (i.button) {
    case 0:
      t = this.mouseButtons.LEFT;
      break;
    case 1:
      t = this.mouseButtons.MIDDLE;
      break;
    case 2:
      t = this.mouseButtons.RIGHT;
      break;
    default:
      t = -1;
  }
  switch (t) {
    case D.DOLLY:
      if (this.enableZoom === !1) return;
      (this._handleMouseDownDolly(i), (this.state = r.DOLLY));
      break;
    case D.ROTATE:
      if (i.ctrlKey || i.metaKey || i.shiftKey) {
        if (this.enablePan === !1) return;
        (this._handleMouseDownPan(i), (this.state = r.PAN));
      } else {
        if (this.enableRotate === !1) return;
        (this._handleMouseDownRotate(i), (this.state = r.ROTATE));
      }
      break;
    case D.PAN:
      if (i.ctrlKey || i.metaKey || i.shiftKey) {
        if (this.enableRotate === !1) return;
        (this._handleMouseDownRotate(i), (this.state = r.ROTATE));
      } else {
        if (this.enablePan === !1) return;
        (this._handleMouseDownPan(i), (this.state = r.PAN));
      }
      break;
    default:
      this.state = r.NONE;
  }
  this.state !== r.NONE && this.dispatchEvent(W);
}
function Lt(i) {
  switch (this.state) {
    case r.ROTATE:
      if (this.enableRotate === !1) return;
      this._handleMouseMoveRotate(i);
      break;
    case r.DOLLY:
      if (this.enableZoom === !1) return;
      this._handleMouseMoveDolly(i);
      break;
    case r.PAN:
      if (this.enablePan === !1) return;
      this._handleMouseMovePan(i);
      break;
  }
}
function Ot(i) {
  this.enabled === !1 ||
    this.enableZoom === !1 ||
    this.state !== r.NONE ||
    (i.preventDefault(),
    this.dispatchEvent(W),
    this._handleMouseWheel(this._customWheelEvent(i)),
    this.dispatchEvent(ht));
}
function jt(i) {
  this.enabled !== !1 && this._handleKeyDown(i);
}
function kt(i) {
  switch ((this._trackPointer(i), this._pointers.length)) {
    case 1:
      switch (this.touches.ONE) {
        case M.ROTATE:
          if (this.enableRotate === !1) return;
          (this._handleTouchStartRotate(i), (this.state = r.TOUCH_ROTATE));
          break;
        case M.PAN:
          if (this.enablePan === !1) return;
          (this._handleTouchStartPan(i), (this.state = r.TOUCH_PAN));
          break;
        default:
          this.state = r.NONE;
      }
      break;
    case 2:
      switch (this.touches.TWO) {
        case M.DOLLY_PAN:
          if (this.enableZoom === !1 && this.enablePan === !1) return;
          (this._handleTouchStartDollyPan(i), (this.state = r.TOUCH_DOLLY_PAN));
          break;
        case M.DOLLY_ROTATE:
          if (this.enableZoom === !1 && this.enableRotate === !1) return;
          (this._handleTouchStartDollyRotate(i),
            (this.state = r.TOUCH_DOLLY_ROTATE));
          break;
        default:
          this.state = r.NONE;
      }
      break;
    default:
      this.state = r.NONE;
  }
  this.state !== r.NONE && this.dispatchEvent(W);
}
function Nt(i) {
  switch ((this._trackPointer(i), this.state)) {
    case r.TOUCH_ROTATE:
      if (this.enableRotate === !1) return;
      (this._handleTouchMoveRotate(i), this.update());
      break;
    case r.TOUCH_PAN:
      if (this.enablePan === !1) return;
      (this._handleTouchMovePan(i), this.update());
      break;
    case r.TOUCH_DOLLY_PAN:
      if (this.enableZoom === !1 && this.enablePan === !1) return;
      (this._handleTouchMoveDollyPan(i), this.update());
      break;
    case r.TOUCH_DOLLY_ROTATE:
      if (this.enableZoom === !1 && this.enableRotate === !1) return;
      (this._handleTouchMoveDollyRotate(i), this.update());
      break;
    default:
      this.state = r.NONE;
  }
}
function It(i) {
  this.enabled !== !1 && i.preventDefault();
}
function zt(i) {
  i.key === "Control" &&
    ((this._controlActive = !0),
    this.domElement
      .getRootNode()
      .addEventListener("keyup", this._interceptControlUp, {
        passive: !0,
        capture: !0,
      }));
}
function Yt(i) {
  i.key === "Control" &&
    ((this._controlActive = !1),
    this.domElement
      .getRootNode()
      .removeEventListener("keyup", this._interceptControlUp, {
        passive: !0,
        capture: !0,
      }));
}
const K = 1.35,
  R = (i, t, e = K + 0.015) => {
    const s = j.degToRad(i),
      o = j.degToRad(t);
    return new E(
      e * Math.cos(s) * Math.cos(o),
      e * Math.sin(s),
      -e * Math.cos(s) * Math.sin(o),
    );
  };
function Ut() {
  const i = document.createElement("canvas");
  ((i.width = 2048), (i.height = 1024));
  const t = i.getContext("2d"),
    e = gt()
      .translate([1024, 512])
      .scale(1024 / Math.PI),
    s = Et(e, t);
  ((t.fillStyle = "#e7edef"),
    t.fillRect(0, 0, 2048, 1024),
    t.beginPath(),
    s(Pt(L, L.objects.countries)),
    (t.fillStyle = "#bdc9c6"),
    t.fill(),
    t.beginPath(),
    s(wt(L, L.objects.countries)),
    (t.strokeStyle = "#8c9c99"),
    (t.lineWidth = 0.85),
    t.stroke(),
    t.beginPath(),
    s(Mt()),
    (t.strokeStyle = "#bcc8c960"),
    (t.lineWidth = 0.65),
    t.stroke());
  const o = new Dt(i);
  return ((o.colorSpace = nt), (o.anisotropy = 8), o);
}
class Ht {
  constructor(t, { onSelect: e, onCluster: s, onRotate: o, onFallback: h }) {
    ((this.container = t),
      (this.onSelect = e),
      (this.onCluster = s),
      (this.onRotate = o),
      (this.onFallback = h),
      (this.records = []),
      (this.active = !0),
      (this.showImages = !0),
      (this.selected = null),
      (this.initialFocusApplied = !1),
      (this.userInteracted = !1),
      (this.width = 1),
      (this.height = 1),
      (this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches),
      (this.renderer = new pt({
        antialias: !0,
        alpha: !0,
        powerPreference: "low-power",
      })),
      this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75)),
      this.renderer.setClearColor(0, 0),
      (this.renderer.outputColorSpace = nt),
      this.renderer.domElement.setAttribute("aria-hidden", "true"),
      this.renderer.domElement.addEventListener("webglcontextlost", (f) => {
        (f.preventDefault(),
          this.stop(),
          this.onFallback?.("3D 渲染暂不可用，事件列表仍可正常阅读。"));
      }),
      t.append(this.renderer.domElement),
      (this.labels = document.createElement("div")),
      (this.labels.className = "globe-labels"),
      t.append(this.labels),
      (this.scene = new mt()),
      (this.camera = new ut(38, 1, 0.1, 100)),
      this.camera.position.copy(R(24, 80, 4.8)),
      this.camera.lookAt(0, 0, 0),
      (this.controls = new xt(this.camera, this.renderer.domElement)),
      (this.controls.enablePan = !1),
      (this.controls.enableDamping = !this.reduced),
      (this.controls.dampingFactor = 0.06),
      (this.controls.minDistance = 2.5),
      (this.controls.maxDistance = 7.2),
      (this.controls.rotateSpeed = 0.55),
      (this.controls.zoomSpeed = 0.65),
      (this.controls.autoRotate = !1),
      (this.controls.autoRotateSpeed = 0.12),
      (this.controls.minPolarAngle = 0.13),
      (this.controls.maxPolarAngle = Math.PI - 0.13),
      this.controls.addEventListener("start", () => {
        ((this.userInteracted = !0),
          (this.focusAnimation = null),
          this.setAutoRotate(!1));
      }),
      (this.earth = new _t(
        new ft(K, 96, 64),
        new bt({ map: Ut(), roughness: 1, metalness: 0 }),
      )),
      this.scene.add(this.earth),
      this.scene.add(new yt("#ffffff", 2.1)));
    const l = new st("#ffffff", 1.4);
    (l.position.set(-3, 5, 4), this.scene.add(l));
    const m = new st("#ffffff", 0.5);
    (m.position.set(3, -2, -4),
      this.scene.add(m),
      (this.resizeObserver = new ResizeObserver(() => this.resize())),
      this.resizeObserver.observe(t),
      (this.visibilityHandler = () => {
        document.hidden || ((this.lastFrame = 0), (this.lastCluster = 0));
      }),
      document.addEventListener("visibilitychange", this.visibilityHandler),
      (this.animate = this.animate.bind(this)),
      this.resize(),
      (this.raf = requestAnimationFrame(this.animate)));
  }
  resize() {
    ((this.width = Math.max(1, this.container.clientWidth)),
      (this.height = Math.max(1, this.container.clientHeight)),
      (this.camera.aspect = this.width / this.height),
      this.camera.updateProjectionMatrix(),
      this.renderer.setSize(this.width, this.height, !1),
      (this.lastCluster = 0));
  }
  setEvents(t, e = new Set()) {
    if (
      ((this.records = t.flatMap((s) =>
        it(s).map((o) => ({
          event: s,
          location: o,
          vector: R(o.latitude, o.longitude),
          isNew: e.has(s.id),
        })),
      )),
      !this.initialFocusApplied &&
        this.records.length &&
        ((this.initialFocusApplied = !0),
        !this.userInteracted && !this.selected))
    ) {
      const s = [...this.records].sort((h, l) => x(l.event) - x(h.event))[0],
        o = R(
          s.location.latitude,
          s.location.longitude,
          this.camera.position.length(),
        );
      this.reduced
        ? (this.camera.position.copy(o), this.controls.update())
        : (this.focusAnimation = {
            start: performance.now(),
            from: this.camera.position.clone(),
            to: o,
          });
    }
    ((this.lastCluster = 0), this.updateClusters());
  }
  setActive(t) {
    ((this.active = !!t), t && ((this.lastFrame = 0), this.resize()));
  }
  setShowImages(t) {
    ((this.showImages = !!t), (this.lastCluster = 0), this.updateClusters());
  }
  setSelected(t) {
    ((this.selected = t), (this.lastCluster = 0));
  }
  focus(t) {
    const e = it(t)[0];
    if (!e) return !1;
    (this.setAutoRotate(!1), (this.selected = t.id));
    const s = R(e.latitude, e.longitude, 3.6);
    return (
      this.reduced
        ? (this.camera.position.copy(s), this.controls.update())
        : (this.focusAnimation = {
            start: performance.now(),
            from: this.camera.position.clone(),
            to: s,
          }),
      (this.lastCluster = 0),
      !0
    );
  }
  setAutoRotate(t, e = !1) {
    (e && ((this.userInteracted = !0), (this.focusAnimation = null)),
      (this.controls.autoRotate = !!t),
      this.onRotate?.(this.controls.autoRotate));
  }
  zoom(t) {
    ((this.userInteracted = !0),
      (this.focusAnimation = null),
      this.camera.position
        .multiplyScalar(t > 0 ? 0.88 : 1.13)
        .clampLength(2.5, 7.2),
      this.controls.update(),
      (this.lastCluster = 0));
  }
  reset() {
    ((this.userInteracted = !0),
      (this.focusAnimation = null),
      this.camera.position.copy(R(24, 80, 4.8)),
      this.controls.target.set(0, 0, 0),
      this.controls.update(),
      (this.selected = null),
      (this.lastCluster = 0));
  }
  project(t) {
    const e = this.camera.position.length();
    if (
      t.vector.dot(this.camera.position) / (t.vector.length() * e) <
      K / e + 0.02
    )
      return null;
    const s = t.vector.clone().project(this.camera),
      o = (s.x * 0.5 + 0.5) * this.width,
      h = (-s.y * 0.5 + 0.5) * this.height;
    return s.z > 1 ||
      o < 12 ||
      h < 12 ||
      o > this.width - 12 ||
      h > this.height - 12
      ? null
      : { x: o, y: h };
  }
  updateClusters() {
    if (!this.labels) return;
    const t = [],
      e = [...this.records].sort(
        (a, c) =>
          +(c.event.id === this.selected) - +(a.event.id === this.selected) ||
          x(c.event) - x(a.event),
      );
    for (const a of e) {
      const c = this.project(a);
      if (!c) continue;
      const n = t.find((p) => Math.hypot(p.p.x - c.x, p.p.y - c.y) < 40);
      n
        ? n.records.some((p) => p.event.id === a.event.id) || n.records.push(a)
        : t.push({ records: [a], p: c, record: a });
    }
    const s = matchMedia("(max-width: 760px)").matches,
      o = this.width < 480,
      h = o ? 236 : 258,
      l = s ? 84 : 104,
      m = this.container.getBoundingClientRect(),
      f = this.container.parentElement.getBoundingClientRect(),
      w = Math.max(12, f.left - m.left + 18),
      S = Math.min(this.width - 12, f.right - m.left - 18),
      k = Math.max(12, f.top - m.top + (s ? 42 : 68)),
      N = Math.min(this.height - 12, f.bottom - m.top - (s ? 64 : 96)),
      I = new Map(),
      z = [],
      X = new Set();
    for (const a of t) {
      if (I.size >= (s ? 1 : 2)) break;
      if (
        X.has(a.record.event.id) ||
        !a.record.event.title ||
        S - w < h ||
        N - k < l
      )
        continue;
      let c = a.p.x + 20;
      (c + h > S && (c = a.p.x - h - 20),
        (c = Math.max(w, Math.min(S - h, c))));
      const n = Math.max(k, Math.min(N - l, a.p.y - l / 2));
      if (Math.abs(n + l / 2 - a.p.y) > (s ? 105 : 90)) continue;
      const p = { left: c, top: n, right: c + h, bottom: n + l };
      z.some(
        (_) =>
          p.left < _.right + 12 &&
          p.right + 12 > _.left &&
          p.top < _.bottom + 12 &&
          p.bottom + 12 > _.top,
      ) || (I.set(a, { left: c, top: n }), z.push(p), X.add(a.record.event.id));
    }
    const Y = new Map([...this.labels.children].map((a) => [a.dataset.key, a])),
      $ = [...z];
    let q = 0;
    t.slice(0, 65).forEach((a) => {
      const c = `${a.record.event.id}:${a.record.location.latitude}:${a.record.location.longitude}`;
      let n = Y.get(c);
      if ((Y.delete(c), !n)) {
        ((n = document.createElement("button")),
          (n.type = "button"),
          (n.className = "map-pin"),
          (n.dataset.key = c));
        const b = document.createElement("span");
        b.className = "pin-dot";
        const v = document.createElement("span");
        v.className = "pin-label";
        const Q = document.createElement("span");
        Q.className = "pin-place";
        const J = document.createElement("span");
        J.className = "pin-headline";
        const F = document.createElement("span");
        ((F.className = "pin-copy"), F.append(Q, J));
        const y = document.createElement("img");
        ((y.className = "pin-image"),
          (y.alt = ""),
          (y.loading = "lazy"),
          (y.decoding = "async"),
          (y.referrerPolicy = "no-referrer"),
          (y.hidden = !0),
          y.addEventListener("error", () => {
            ((y.dataset.failedSrc = y.getAttribute("src") || ""),
              (y.hidden = !0),
              v.classList.remove("has-image"));
          }),
          v.append(F, y),
          n.append(b, v),
          n.addEventListener("click", () => {
            const C = n._group.records;
            C.length > 1
              ? this.onCluster?.(
                  C.map((rt) => rt.event),
                  C[0].location.name,
                )
              : this.onSelect?.(C[0].event.id);
          }),
          n.addEventListener("focus", () => this.setAutoRotate(!1)),
          this.labels.append(n));
      }
      n._group = a;
      const p = a.records.length;
      (n.classList.toggle("is-cluster", p > 1),
        n.classList.toggle(
          "is-selected",
          a.records.some((b) => b.event.id === this.selected),
        ),
        n.classList.toggle(
          "is-new",
          a.records.some((b) => b.isNew),
        ));
      const _ = I.get(a);
      (n.classList.toggle("has-preview", !!_),
        n.classList.toggle("compact-preview", !!_ && o),
        (n._preview = _ || null),
        _ &&
          (n.style.setProperty("--preview-left", `${_.left - a.p.x + 18}px`),
          n.style.setProperty("--preview-top", `${_.top - a.p.y + 18}px`)),
        n.classList.toggle("is-high", x(a.record.event) >= 80),
        (n.children[0].textContent = p > 1 ? String(p) : ""));
      const B = `${a.record.location.name || "事件位置"}${p > 1 ? ` · ${p} 个事件` : ""}`;
      ((n.querySelector(".pin-place").textContent = B),
        (n.querySelector(".pin-headline").textContent =
          a.record.event.title || ""));
      const U = Math.min(148, Array.from(B).length * 11 + 8),
        Z = a.p.x + 20 + U > S ? a.p.x - U - 20 : a.p.x + 20,
        P = { left: Z, top: a.p.y - 10, right: Z + U, bottom: a.p.y + 12 },
        V =
          !_ &&
          !s &&
          q < 3 &&
          P.left >= w &&
          P.right <= S &&
          P.top >= k &&
          P.bottom <= N &&
          !$.some(
            (b) =>
              P.left < b.right + 10 &&
              P.right + 10 > b.left &&
              P.top < b.bottom + 8 &&
              P.bottom + 8 > b.top,
          );
      (n.classList.toggle("show-label", V),
        n.style.setProperty("--label-left", `${Z - a.p.x + 18}px`),
        V && ($.push(P), (q += 1)));
      const A = this.showImages && _ ? St(a.record.event)[0] : null,
        T = n.querySelector(".pin-image"),
        G = A && T.dataset.failedSrc !== A.thumbnail_url;
      (n.querySelector(".pin-label").classList.toggle("has-image", !!G),
        G
          ? ((T.hidden = !1),
            T.getAttribute("src") !== A.thumbnail_url &&
              (T.src = A.thumbnail_url))
          : (T.hidden = !0),
        n.setAttribute(
          "aria-label",
          p > 1
            ? `${a.record.location.name || "此区域"}，${p} 个事件，重点：${a.record.event.title}。点击展开`
            : `${a.record.location.name || "事件位置"}：${a.record.event.title}`,
        ),
        (n.title = a.record.event.title || ""),
        (n.style.transform = `translate(${a.p.x}px, ${a.p.y}px)`));
    });
    for (const a of Y.values()) a.remove();
  }
  animate(t) {
    if (
      ((this.raf = requestAnimationFrame(this.animate)),
      !(
        !this.active ||
        document.hidden ||
        t - (this.lastFrame || 0) < (this.reduced ? 100 : 32)
      ))
    ) {
      if (((this.lastFrame = t), this.focusAnimation)) {
        const e = Math.min(1, (t - this.focusAnimation.start) / 950),
          s = 1 - Math.pow(1 - e, 3),
          o = this.focusAnimation.from,
          h = this.focusAnimation.to,
          l = o.clone().normalize().lerp(h.clone().normalize(), s).normalize();
        (this.camera.position.copy(
          l.multiplyScalar(j.lerp(o.length(), h.length(), s)),
        ),
          e >= 1 && (this.focusAnimation = null));
      }
      if ((this.controls.update(), t - (this.lastCluster || 0) > 250))
        (this.updateClusters(), (this.lastCluster = t));
      else
        for (const e of this.labels.children) {
          const s = this.project(e._group.record);
          ((e.style.visibility = s ? "visible" : "hidden"),
            s &&
              ((e.style.transform = `translate(${s.x}px, ${s.y}px)`),
              e._preview &&
                (e.style.setProperty(
                  "--preview-left",
                  `${e._preview.left - s.x + 18}px`,
                ),
                e.style.setProperty(
                  "--preview-top",
                  `${e._preview.top - s.y + 18}px`,
                ))));
        }
      this.renderer.render(this.scene, this.camera);
    }
  }
  stop() {
    cancelAnimationFrame(this.raf);
  }
  destroy() {
    (this.stop(),
      this.resizeObserver.disconnect(),
      this.controls.dispose(),
      document.removeEventListener("visibilitychange", this.visibilityHandler),
      this.scene.traverse((t) => {
        (t.geometry?.dispose(),
          t.material && (t.material.map?.dispose(), t.material.dispose()));
      }),
      this.renderer.dispose(),
      this.renderer.domElement.remove(),
      this.labels.remove());
  }
}
export { Ht as FrontierGlobe };
