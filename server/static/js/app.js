/* ============================================================================
   FRIBOI ONLINE — app.js
   Vanilla JS, sem dependências. Responsável por:
     · carrinho (add / update / remove via fetch, com contador no header)
     · autenticação (login, cadastro, logout)
     · carrossel das vitrines e do hero
     · abas da página de produto
     · filtros / ordenação do catálogo
     · menu mobile
     · toasts e validações em PT-BR
   ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------- helpers */
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  function brl(value) {
    var n = Number(value);
    if (!isFinite(n)) n = 0;
    return 'R$ ' + n.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function parseJSON(text) {
    try { return JSON.parse(text); } catch (e) { return null; }
  }

  /* ------------------------------------------------------------------ toast */
  var toastEl = null;
  var toastTimer = null;

  function toast(message, isError) {
    if (!toastEl) toastEl = $('[data-toast]');
    if (!toastEl) return;
    var text = $('[data-toast-text]', toastEl);
    if (text) text.textContent = message;
    toastEl.classList.toggle('is-error', !!isError);
    toastEl.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove('is-visible');
    }, 3200);
  }
  window.friboiToast = toast;

  /* --------------------------------------------------------------- imagens */
  // Qualquer <img> que falhe é marcado com .img-missing (display:none) e o
  // fallback em CSS (logo em texto, banners desenhados, cards de marca) entra.
  // O listener cobre falhas futuras; a varredura no boot cobre as imagens que
  // já falharam antes deste script (defer) ser executado.
  document.addEventListener('error', function (event) {
    var el = event.target;
    if (el && el.tagName === 'IMG') el.classList.add('img-missing');
  }, true);

  function markMissingImages() {
    Array.prototype.forEach.call(document.images, function (img) {
      if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) {
        img.classList.add('img-missing');
      }
    });
  }

  /* ---------------------------------------------------------------- fetch  */
  function api(url, options) {
    options = options || {};
    var config = {
      method: options.method || 'GET',
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    };
    if (options.body !== undefined) {
      config.headers['Content-Type'] = 'application/json';
      config.body = JSON.stringify(options.body);
    }
    return fetch(url, config).then(function (response) {
      return response.text().then(function (text) {
        var data = parseJSON(text);
        if (!response.ok) {
          var detail = 'Não foi possível concluir a operação.';
          if (data && data.detail) {
            detail = typeof data.detail === 'string'
              ? data.detail
              : (data.detail[0] && data.detail[0].msg) || detail;
          }
          var err = new Error(detail);
          err.status = response.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  /* ---------------------------------------------------------------- carrinho */
  function updateCartBadge(count) {
    $$('[data-cart-count]').forEach(function (el) {
      el.textContent = count;
      el.setAttribute('data-empty', count > 0 ? 'false' : 'true');
    });
  }

  function addToCart(productId, qty, name) {
    return api('/api/cart/items', { method: 'POST', body: { product_id: productId, qty: qty || 1 } })
      .then(function (cart) {
        updateCartBadge(cart.count || 0);
        toast('Adicionado ao Carrinho' + (name ? ' — ' + name : ''));
        return cart;
      });
  }

  function refreshCart() {
    return api('/api/cart').then(function (cart) {
      updateCartBadge(cart.count || 0);
      return cart;
    }).catch(function () { return null; });
  }

  function renderCartLines(cart) {
    var list = $('[data-cart-list]');
    if (!list || !cart) return;
    var items = cart.items || [];
    if (!items.length) {
      window.location.reload();
      return;
    }
    items.forEach(function (item) {
      var row = list.querySelector('[data-cart-item="' + item.product_id + '"]');
      if (!row) return;
      var qtyInput = $('[data-cart-qty]', row);
      var sub = $('[data-cart-subtotal]', row);
      if (qtyInput && document.activeElement !== qtyInput) qtyInput.value = item.qty;
      if (sub) sub.textContent = brl(item.subtotal);
    });
    $$('[data-cart-subtotal-total]').forEach(function (el) { el.textContent = brl(cart.subtotal); });
    $$('[data-cart-total]').forEach(function (el) { el.textContent = brl(cart.total || cart.subtotal); });
  }

  /* ----------------------------------------------------------- carrinho DOM */
  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-add-to-cart-form]');
    if (!form) return;
    event.preventDefault();

    var id = form.getAttribute('data-product-id');
    var input = $('[data-qty-input]', form);
    var qty = input ? parseInt(input.value, 10) || 1 : 1;
    var max = form.getAttribute('data-max-qty');
    if (max && qty > parseInt(max, 10)) qty = parseInt(max, 10);
    if (qty < 1) qty = 1;

    var button = $('.btn-add-cart', form);
    var feedback = $('[data-add-feedback]');
    if (button) button.disabled = true;

    addToCart(id, qty, form.getAttribute('data-product-name'))
      .then(function () {
        if (feedback) {
          feedback.textContent = qty + 'x adicionado ao carrinho.';
          feedback.classList.add('is-visible');
          feedback.classList.remove('is-error');
        }
      })
      .catch(function (err) {
        if (feedback) {
          feedback.textContent = err.message || 'Não foi possível adicionar ao carrinho.';
          feedback.classList.add('is-visible', 'is-error');
        } else {
          toast(err.message || 'Não foi possível adicionar ao carrinho.', true);
        }
      })
      .then(function () {
        if (button) button.disabled = false;
      });
  });

  document.addEventListener('click', function (event) {
    var minus = event.target.closest('[data-qty-minus]');
    var plus = event.target.closest('[data-qty-plus]');
    if (minus || plus) {
      var form = (minus || plus).closest('[data-add-to-cart-form]');
      var input = form ? $('[data-qty-input]', form) : null;
      if (!input) return;
      var value = parseInt(input.value, 10) || 1;
      var max = parseInt(input.getAttribute('max'), 10) || 99;
      value += (plus ? 1 : -1);
      if (value < 1) value = 1;
      if (value > max) value = max;
      input.value = value;
      return;
    }

    // carrinho: + / - / remover
    var row = event.target.closest('[data-cart-item]');
    if (row) {
      var id = row.getAttribute('data-cart-item');
      var qtyInput = $('[data-cart-qty]', row);
      var current = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;

      if (event.target.closest('[data-cart-plus]')) {
        updateCartItem(id, current + 1, row);
        return;
      }
      if (event.target.closest('[data-cart-minus]')) {
        updateCartItem(id, current - 1, row);
        return;
      }
      if (event.target.closest('[data-cart-remove]')) {
        api('/api/cart/items/' + encodeURIComponent(id), { method: 'DELETE' })
          .then(function (cart) {
            row.parentNode.removeChild(row);
            updateCartBadge(cart.count || 0);
            renderCartLines(cart);
            toast('Produto removido do carrinho');
          })
          .catch(function (err) { toast(err.message || 'Erro ao remover.', true); });
        return;
      }
    }
  });

  document.addEventListener('change', function (event) {
    var input = event.target.closest('[data-cart-qty]');
    if (!input) return;
    var row = input.closest('[data-cart-item]');
    var id = row ? row.getAttribute('data-cart-item') : null;
    if (!id) return;
    var qty = parseInt(input.value, 10) || 1;
    updateCartItem(id, qty, row);
  });

  function updateCartItem(productId, qty, row) {
    if (qty < 1) qty = 1;
    api('/api/cart/items/' + encodeURIComponent(productId), { method: 'PATCH', body: { qty: qty } })
      .then(function (cart) {
        updateCartBadge(cart.count || 0);
        renderCartLines(cart);
        if (row) {
          var input = $('[data-cart-qty]', row);
          if (input) input.value = qty;
        }
      })
      .catch(function (err) { toast(err.message || 'Erro ao atualizar o carrinho.', true); });
  }

  /* ------------------------------------------------------------- autenticação */
  function setFormAlert(form, message, kind) {
    var scope = form ? form.closest('.auth-card, .checkout-page, form') : null;
    var alertEl = (scope && $('[data-form-alert]', scope)) || $('[data-form-alert]');
    if (!alertEl) { toast(message, kind !== 'success'); return; }
    alertEl.textContent = message;
    alertEl.classList.add('is-visible');
    alertEl.classList.toggle('is-error', kind !== 'success');
    alertEl.classList.toggle('is-success', kind === 'success');
  }

  function fieldError(input, message) {
    var field = input.closest('.field');
    if (!field) return;
    field.classList.add('has-error');
    var err = $('[data-error]', field);
    if (err && message) err.textContent = message;
  }

  function clearErrors(form) {
    $$('.field', form).forEach(function (f) { f.classList.remove('has-error'); });
    var alertEl = form.closest('.auth-card, .checkout-page');
    var a = alertEl ? $('[data-form-alert]', alertEl) : null;
    if (a) a.classList.remove('is-visible', 'is-error', 'is-success');
  }

  function onlyDigits(v) { return (v || '').replace(/\D+/g, ''); }

  document.addEventListener('submit', function (event) {
    var form = event.target;

    /* ---- login ---- */
    if (form.matches('[data-login-form]')) {
      event.preventDefault();
      clearErrors(form);
      var email = form.email.value.trim();
      var password = form.password.value;
      var ok = true;
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        fieldError(form.email, 'Informe um e-mail válido.');
        ok = false;
      }
      if (!password) { fieldError(form.password, 'Informe a sua senha.'); ok = false; }
      if (!ok) return;

      var submit = $('[data-submit]', form);
      if (submit) submit.disabled = true;
      api('/api/auth/login', { method: 'POST', body: { email: email, password: password } })
        .then(function (data) {
          setFormAlert(form, 'Login realizado com sucesso. Redirecionando…', 'success');
          var next = form.next ? form.next.value : '/';
          api('/api/cart/merge', { method: 'POST' }).catch(function () { });
          setTimeout(function () { window.location.href = next || '/'; }, 350);
        })
        .catch(function (err) {
          setFormAlert(form, err.message || 'E-mail ou senha inválidos', 'error');
          if (submit) submit.disabled = false;
        });
      return;
    }

    /* ---- cadastro ---- */
    if (form.matches('[data-register-form]')) {
      event.preventDefault();
      clearErrors(form);
      var name = form.name.value.trim();
      var mail = form.email.value.trim();
      var pass = form.password.value;
      var pass2 = form.password_confirm.value;
      var cpf = onlyDigits(form.cpf.value);
      var phone = onlyDigits(form.phone.value);
      var valid = true;

      if (name.length < 3) { fieldError(form.name, 'Informe o seu nome completo.'); valid = false; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) { fieldError(form.email, 'Informe um e-mail válido.'); valid = false; }
      if (cpf && cpf.length !== 11) { fieldError(form.cpf, 'O CPF deve ter 11 dígitos.'); valid = false; }
      if (phone && (phone.length < 10 || phone.length > 11)) { fieldError(form.phone, 'Telefone inválido.'); valid = false; }
      if (pass.length < 6) { fieldError(form.password, 'A senha precisa ter no mínimo 6 caracteres.'); valid = false; }
      if (pass !== pass2) { fieldError(form.password_confirm, 'As senhas não conferem.'); valid = false; }
      if (!valid) return;

      var btn = $('[data-submit]', form);
      if (btn) btn.disabled = true;

      var payload = { name: name, email: mail, password: pass };
      if (cpf) payload.cpf = cpf;
      if (phone) payload.phone = phone;

      api('/api/auth/register', { method: 'POST', body: payload })
        .then(function () {
          return api('/api/auth/login', { method: 'POST', body: { email: mail, password: pass } });
        })
        .then(function () {
          setFormAlert(form, 'Conta criada com sucesso. Redirecionando…', 'success');
          api('/api/cart/merge', { method: 'POST' }).catch(function () { });
          var next = form.next ? form.next.value : '/';
          setTimeout(function () { window.location.href = next || '/'; }, 400);
        })
        .catch(function (err) {
          setFormAlert(form, err.message || 'Não foi possível criar a conta.', 'error');
          if (btn) btn.disabled = false;
        });
      return;
    }
  });

  /* ---- logout (link) ---- */
  document.addEventListener('click', function (event) {
    var link = event.target.closest('[data-logout]');
    if (!link) return;
    event.preventDefault();
    api('/api/auth/logout', { method: 'POST' })
      .catch(function () { })
      .then(function () { window.location.href = '/'; });
  });

  /* ------------------------------------------------------------ checkout */
  document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-checkout-submit]');
    if (!btn) return;
    var form = $('[data-checkout-form]');
    if (!form) return;

    var shipName = $('#ship_name', form);
    var cep = $('#ship_cep', form);
    var ok = true;
    if (!shipName || shipName.value.trim().length < 3) { if (shipName) fieldError(shipName); ok = false; }
    if (!cep || onlyDigits(cep.value).length !== 8) { if (cep) fieldError(cep, 'Informe um CEP válido com 8 dígitos.'); ok = false; }
    if (!ok) { setFormAlert(form, 'Confira os campos destacados antes de continuar.', 'error'); return; }

    var paymentEl = form.querySelector('input[name="payment"]:checked');
    var payload = {
      payment: paymentEl ? paymentEl.value : 'pix',
      ship: {
        name: shipName.value.trim(),
        email: $('#ship_email', form) ? $('#ship_email', form).value.trim() : '',
        phone: $('#ship_phone', form) ? onlyDigits($('#ship_phone', form).value) : '',
        cep: onlyDigits(cep.value),
        address: $('#ship_address', form) ? $('#ship_address', form).value.trim() : '',
        number: $('#ship_number', form) ? $('#ship_number', form).value.trim() : '',
        complement: $('#ship_complement', form) ? $('#ship_complement', form).value.trim() : '',
        district: $('#ship_district', form) ? $('#ship_district', form).value.trim() : '',
        city: $('#ship_city', form) ? $('#ship_city', form).value.trim() : '',
        state: $('#ship_state', form) ? $('#ship_state', form).value.trim().toUpperCase() : ''
      }
    };

    btn.disabled = true;
    api('/api/checkout', { method: 'POST', body: payload })
      .then(function (data) {
        var order = data && data.order ? data.order : data;
        updateCartBadge(0);
        toast('Pedido #' + (order && order.id ? order.id : '') + ' criado com sucesso!');
        setTimeout(function () { window.location.href = '/conta'; }, 900);
      })
      .catch(function (err) {
        setFormAlert(form, err.message || 'Não foi possível finalizar o pedido.', 'error');
        btn.disabled = false;
      });
  });

  /* ------------------------------------------------------------------ hero */
  function initHero() {
    var hero = $('[data-hero]');
    if (!hero) return;
    var slides = $$('.hero-slide', hero);
    var dots = $$('.hero-dots button', hero);
    if (!slides.length) return;
    var index = slides.findIndex(function (s) { return s.classList.contains('is-active'); });
    if (index < 0) index = 0;
    var timer = null;

    function show(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) { s.classList.toggle('is-active', n === index); });
      dots.forEach(function (d, n) {
        d.classList.toggle('is-active', n === index);
        d.setAttribute('aria-selected', n === index ? 'true' : 'false');
      });
    }
    function play() {
      stop();
      timer = setInterval(function () { show(index + 1); }, 6000);
    }
    function stop() { if (timer) clearInterval(timer); timer = null; }

    dots.forEach(function (dot, n) {
      dot.addEventListener('click', function () { show(n); play(); });
    });
    var prev = $('[data-hero-prev]', hero);
    var next = $('[data-hero-next]', hero);
    if (prev) prev.addEventListener('click', function () { show(index - 1); play(); });
    if (next) next.addEventListener('click', function () { show(index + 1); play(); });

    hero.addEventListener('mouseenter', stop);
    hero.addEventListener('mouseleave', play);
    show(index);
    if (slides.length > 1) play();
  }

  /* -------------------------------------------------------------- carrossel */
  function initCarousels() {
    $$('[data-carousel]').forEach(function (root) {
      var track = $('[data-carousel-track]', root);
      var prev = $('[data-carousel-prev]', root);
      var next = $('[data-carousel-next]', root);
      if (!track || !prev || !next) return;

      function step() {
        var card = track.querySelector('.product-card');
        if (!card) return 270;
        var rect = card.getBoundingClientRect();
        var gap = parseFloat(window.getComputedStyle(track).columnGap || '15') || 15;
        return rect.width + gap;
      }
      function maxScroll() { return Math.max(0, track.scrollWidth - track.clientWidth); }

      function update() { /* setas sempre ativas, com volta (como no original) */ }

      // rolagem horizontal nativa dentro do wrapper (overflow:hidden nunca rola,
      // então o wrapper é scrollável via JS)
      var wrap = track.parentNode;
      wrap.style.overflowX = 'auto';
      wrap.style.scrollBehavior = 'smooth';
      wrap.style.scrollbarWidth = 'none';
      wrap.addEventListener('scroll', update);

      prev.addEventListener('click', function () {
        if (wrap.scrollLeft <= 2) {
          wrap.scrollLeft = maxScroll();
        } else {
          wrap.scrollLeft -= step();
        }
      });
      next.addEventListener('click', function () {
        if (wrap.scrollLeft >= maxScroll() - 2) {
          wrap.scrollLeft = 0;
        } else {
          wrap.scrollLeft += step();
        }
      });
      update();
    });
  }

  /* ------------------------------------------------------------- acordeões */
  function initAccordions() {
    $$('[data-acc-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item = btn.closest('.accordion-item');
        if (!item) return;
        var open = item.classList.toggle('is-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
  }

  /* ------------------------------------------------------------------ abas */
  function initTabs() {
    $$('[data-tabs]').forEach(function (root) {
      var buttons = $$('[data-tab]', root);
      var panels = $$('[data-panel]', root);
      buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          var target = btn.getAttribute('data-tab');
          buttons.forEach(function (b) {
            var on = b === btn;
            b.classList.toggle('is-active', on);
            b.setAttribute('aria-selected', on ? 'true' : 'false');
          });
          panels.forEach(function (panel) {
            panel.classList.toggle('is-active', panel.getAttribute('data-panel') === target);
          });
        });
      });
    });
  }

  /* -------------------------------------------------------------- galeria */
  function initGallery() {
    var main = $('#pdp-main-image');
    if (!main) return;
    $$('[data-thumb]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        $$('[data-thumb]').forEach(function (b) { b.classList.remove('is-active'); });
        btn.classList.add('is-active');
        main.src = btn.getAttribute('data-thumb');
      });
    });
  }

  /* ---------------------------------------------------------------- filtros */
  function initFilters() {
    $$('[data-auto-submit]').forEach(function (select) {
      select.addEventListener('change', function () {
        if (select.form) select.form.submit();
      });
    });
    $$('[data-filters-form] input[type="checkbox"]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        if (cb.form) cb.form.submit();
      });
    });
    $$('.payment-option input').forEach(function (radio) {
      radio.addEventListener('change', function () {
        $$('.payment-option').forEach(function (l) { l.classList.remove('is-selected'); });
        var label = radio.closest('.payment-option');
        if (label) label.classList.add('is-selected');
      });
    });
  }

  /* ------------------------------------------------------------ máscaras */
  function applyMask(input) {
    var kind = input.getAttribute('data-mask');
    input.addEventListener('input', function () {
      var v = onlyDigits(input.value);
      if (kind === 'cpf') {
        v = v.slice(0, 11);
        v = v.replace(/(\d{3})(\d)/, '$1.$2')
             .replace(/(\d{3})(\d)/, '$1.$2')
             .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
      } else if (kind === 'phone') {
        v = v.slice(0, 11);
        if (v.length > 10) {
          v = v.replace(/(\d{2})(\d{5})(\d{0,4})/, '($1) $2-$3');
        } else {
          v = v.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
        }
      } else if (kind === 'cep') {
        v = v.slice(0, 8).replace(/(\d{5})(\d{0,3})/, '$1-$2');
      }
      input.value = v;
    });
  }

  /* -------------------------------------------------- header que colapsa */
  function initHeaderCollapse() {
    var header = document.querySelector('.site-header');
    if (!header) return;
    var onScroll = function () {
      header.classList.toggle('no-top', window.scrollY > 200);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ------------------------------------------------------------ menu mobile */
  function initMobileMenu() {
    var toggle = $('[data-menu-toggle]');
    var nav = $('[data-mobile-nav]');
    if (!toggle || !nav) return;
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ------------------------------------------------------------------- boot */
  function boot() {
    markMissingImages();
    initHero();
    initCarousels();
    initAccordions();
    initTabs();
    initHeaderCollapse();
    initGallery();
    initFilters();
    initMobileMenu();
    $$('[data-mask]').forEach(applyMask);
    refreshCart();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
