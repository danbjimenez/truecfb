/* TrueCFB: the team index. Old team links (team.html#team=Utah&season=2019) move to the team's own page. */
(() => {
  const h = TC.readHash();
  if(h.team) location.replace(TC.teamHref(h.team, h.season));
})();
