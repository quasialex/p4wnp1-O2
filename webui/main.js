new Vue({
    el: '#q-app',
    data: {
        payloads: []
    },
    methods: {
        fetchPayloads() {
            fetch('/api/payloads').then(r => r.json()).then(d => { this.payloads = d; });
        },
        runPayload(p) {
            fetch('/api/run/' + p, {method: 'POST'})
                .then(r => r.text())
                .then(t => this.$q.notify({message: t, timeout: 2000}));
        }
    },
    mounted() {
        this.fetchPayloads();
    }
});
