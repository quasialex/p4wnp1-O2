new Vue({
    el: '#q-app',
    data: {
        payloads: {},
        tab: 'payloads',
        logText: ''
    },
    methods: {
        fetchPayloads() {
            fetch('/api/payloads').then(r => r.json()).then(d => { this.payloads = d; });
        },
        toggleEnabled(name, val) {
            fetch('/api/payloads/' + name, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: val})
            });
        },
        runPayload(p) {
            fetch('/api/run/' + p, {method: 'POST'})
                .then(r => r.text())
                .then(t => this.$q.notify({message: t, timeout: 2000}));
        },
        fetchLog() {
            fetch('/api/log').then(r => r.text()).then(t => { this.logText = t; });
        }
    },
    mounted() {
        this.fetchPayloads();
    },
    watch: {
        tab(val) {
            if (val === 'log') {
                this.fetchLog();
            }
        }
    }
});
