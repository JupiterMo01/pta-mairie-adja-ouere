// ── PTA Mairie d'Adja-Ouèrè ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {

  // Auto-fermeture des alertes après 5 secondes
  setTimeout(function () {
    document.querySelectorAll('.alert.fade.show').forEach(function (el) {
      var bsAlert = bootstrap.Alert.getInstance(el) || new bootstrap.Alert(el);
      bsAlert.close();
    });
  }, 5000);

  // ── Aller directement à l'élément ciblé après une action (go=TYPE-ID) ──────
  var go = new URLSearchParams(window.location.search).get('go');
  if (go) {
    var target = document.getElementById('row-' + go);
    if (target) {
      target.scrollIntoView({ behavior: 'instant', block: 'center' });
      target.classList.add('goto-highlight');
      setTimeout(function () { target.classList.remove('goto-highlight'); }, 2600);
    }
    history.replaceState(null, '', window.location.pathname);
  }

  // Réinitialiser insert_after quand le modal inline se ferme
  document.querySelectorAll('.modal').forEach(function (modal) {
    modal.addEventListener('hidden.bs.modal', function () {
      var field = modal.querySelector('input[name="insert_after"]');
      if (field) field.value = '';
    });
  });

});

// Impression de la page courante
function imprimerPage() {
  window.print();
}

// ── Modal dynamique AJAX ────────────────────────────────────────────────────
// Charge le contenu HTML d'un modal via AJAX et l'injecte dans #ptaDynModalDialog.
// createContextualFragment() exécute les scripts inclus dans le fragment chargé.
function openPtaModal(url) {
  var wrapper = document.getElementById('ptaDynModal');
  if (!wrapper) return;          // pas en mode can_edit
  var dialog  = document.getElementById('ptaDynModalDialog');

  // Affiche un spinner immédiatement
  dialog.innerHTML = [
    '<div class="modal-dialog modal-xl">',
    '  <div class="modal-content p-5 text-center">',
    '    <div class="spinner-border text-primary mx-auto mb-2" role="status"></div>',
    '    <div class="text-muted small">Chargement…</div>',
    '  </div>',
    '</div>'
  ].join('');

  var bsModal = bootstrap.Modal.getOrCreateInstance(wrapper);
  bsModal.show();

  fetch(url)
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    })
    .then(function (html) {
      dialog.innerHTML = '';
      // createContextualFragment exécute les <script> embarqués dans le fragment
      var frag = document.createRange().createContextualFragment(html);
      dialog.appendChild(frag);
    })
    .catch(function (err) {
      dialog.innerHTML = [
        '<div class="modal-dialog">',
        '  <div class="modal-content">',
        '    <div class="modal-header bg-danger text-white">',
        '      <h5 class="modal-title">Erreur de chargement</h5>',
        '      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>',
        '    </div>',
        '    <div class="modal-body text-danger">',
        '      Impossible de charger le formulaire.<br>',
        '      Actualisez la page et réessayez.',
        '    </div>',
        '  </div>',
        '</div>'
      ].join('');
    });
}

// Insérer tâche en dessous d'une tâche existante (AJAX)
function insertTacheBeneath(actId, ordre) {
  openPtaModal('/pta/activite/' + actId + '/modal-add-tache?insert_after=' + ordre);
}

// Insérer activité en dessous d'une activité existante (AJAX)
function insertActiviteBeneath(projId, numero) {
  openPtaModal('/pta/projet/' + projId + '/modal-add-activite?insert_after=' + numero);
}

// Vider insert_after avant d'ouvrir un modal inline (non-AJAX, conservé pour compatibilité)
function clearInsertAfter(modalId) {
  var modal = document.getElementById(modalId);
  if (!modal) return;
  var field = modal.querySelector('input[name="insert_after"]');
  if (field) field.value = '';
}

// Changer valeur hidden puis soumettre le formulaire (duplicate placement)
function setAndSubmit(fieldId, value, formId) {
  document.getElementById(fieldId).value = value;
  document.getElementById(formId).submit();
}