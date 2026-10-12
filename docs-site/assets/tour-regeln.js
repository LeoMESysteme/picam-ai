/* Projekt-Tour, Kapitel „Regeln“ (docs/uebersicht/projekt-tour.md, Abschnitt
 * #regeln). Szenen melden sich über window.dispreadTour.register an; Helfer und
 * Konventionen stehen in tour.js unter „Schnittstelle Kapitel“. */
(function () {
  "use strict";

  const T = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });
  void T;
})();
