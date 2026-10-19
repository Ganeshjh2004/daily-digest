const SVG_NS = "http://www.w3.org/2000/svg";

function icon(paths, label = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "20");
  svg.setAttribute("height", "20");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", label ? "false" : "true");
  if (label) svg.setAttribute("aria-label", label);
  paths.forEach(([tag, attributes]) => {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
    svg.append(node);
  });
  return svg;
}

export const icons = {
  newspaper: () => icon([["path", { d: "M4 5h16v14H4z" }], ["path", { d: "M8 9h8M8 13h8M8 17h5" }]]),
  search: () => icon([["circle", { cx: "11", cy: "11", r: "6" }], ["path", { d: "m16 16 4 4" }]]),
  bookmark: () => icon([["path", { d: "M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-4-6 4z" }]]),
  play: () => icon([["path", { d: "m8 5 11 7-11 7z" }]]),
  calendar: () => icon([["rect", { x: "3", y: "5", width: "18", height: "16", rx: "2" }], ["path", { d: "M16 3v4M8 3v4M3 10h18" }]]),
  refresh: () => icon([["path", { d: "M20 11a8 8 0 1 0 2 5" }], ["path", { d: "M20 4v7h-7" }]]),
  info: () => icon([["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 11v5M12 8h.01" }]]),
  clock: () => icon([["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 7v5l3 2" }]]),
  chart: () => icon([["path", { d: "M4 19V9M10 19V5M16 19v-7M22 19H2" }]]),
};
