/* Included by ool-zero-native.py after the production headers and legacy types. */
extern void abort(void);
extern void exit(int);
extern int puts(const char *);
extern int printf(const char *, ...);
#undef panic
void panic(const char *format, ...) { puts(format); exit(1); }
#define CHECK(x) do { if (!(x)) { puts("FAIL: " #x); exit(1); } } while (0)
vm_size_t msg_ool_size_small;
#define MSG_OOL_SIZE_SMALL msg_ool_size_small
static const vm_size_t ipc_kmsg_max_vm_space = 16384;
static vm_map_t ipc_kernel_copy_map;
static unsigned int allocations, copies, mappings, cleaned;
static unsigned char storage[16384];

static kern_return_t test_allocate(vm_map_t map, vm_offset_t *addr,
    vm_size_t size, int flags, int tag) {
    (void)map; (void)flags; (void)tag;
    CHECK(size && size <= sizeof(storage));
    ++allocations;
    *addr = (vm_offset_t)storage;
    return KERN_SUCCESS;
}
static int test_copyin(mach_vm_offset_t addr, char *dest, vm_size_t size) {
    CHECK(addr == 0x1000 && size == 5);
    memcpy(dest, "hello", size);
    ++copies;
    return 0;
}
static kern_return_t test_map_copyin(vm_map_t map, vm_map_address_t addr,
    vm_map_size_t size, boolean_t dealloc, vm_map_copy_t *copy) {
    (void)map; (void)dealloc;
    CHECK(size == 5);
    CHECK(addr == 0x1000 || addr == (vm_map_address_t)storage);
    ++mappings;
    *copy = (vm_map_copy_t)storage;
    return KERN_SUCCESS;
}
#define vm_allocate_kernel test_allocate
#undef copyin
#define copyin test_copyin
#undef vm_map_copyin
#define vm_map_copyin test_map_copyin
#define ipc_kmsg_clean_partial(...) (++cleaned)
#define ipc_kmsg_copyin_port_descriptor(...) (abort(), (mach_msg_descriptor_t *)0)
#define ipc_kmsg_copyin_ool_ports_descriptor(...) (abort(), (mach_msg_descriptor_t *)0)
#define ipc_kmsg_copyin_guarded_port_descriptor(...) (abort(), (mach_msg_descriptor_t *)0)

/* PRODUCTION_FUNCTIONS */

static void run(int wide, int type, int copy, int dealloc,
    unsigned long long addr, unsigned int size, int mixed,
    mach_msg_return_t expected) {
    /* Headroom for the real 32-bit to kernel descriptor expansion. */
    unsigned char bytes[256] __attribute__((aligned(16))) = {0};
    mach_msg_base_t *base = (void *)(bytes + 64);
    struct ipc_port port = {0};
    struct ipc_kmsg kmsg = {0};
    struct _vm_map map = {0};
    mach_msg_option_t options = 0;
    map.max_offset = wide ? MACH_VM_MAX_ADDRESS : VM_MAX_ADDRESS;
    base->header.msgh_remote_port = &port;
    base->header.msgh_bits = MACH_MSGH_BITS_COMPLEX;
    base->body.msgh_descriptor_count = mixed ? 3 : 1;
    unsigned char *next = (void *)(base + 1);
    unsigned int wire_size = wide ? sizeof(mach_msg_ool_descriptor64_t) : sizeof(mach_msg_ool_descriptor32_t);
    for (unsigned int i = 0; i < base->body.msgh_descriptor_count; ++i) {
        unsigned int length = mixed && i == 1 ? 5 : size;
        unsigned long long source = length ? 0x1000 : addr;
        if (wide) {
            mach_msg_ool_descriptor64_t *d = (void *)next;
            d->address = source; d->size = length; d->deallocate = dealloc;
            d->copy = copy; d->type = type;
        } else {
            mach_msg_ool_descriptor32_t *d = (void *)next;
            d->address = (unsigned int)source; d->size = length; d->deallocate = dealloc;
            d->copy = copy; d->type = type;
        }
        next += wire_size;
    }
    base->header.msgh_size = next - (unsigned char *)base;
    kmsg.ikm_header = &base->header;
    allocations = copies = mappings = cleaned = 0;
    mach_msg_return_t result = ipc_kmsg_copyin_body(&kmsg, NULL, &map, &options);
    if (result != expected) printf("wide=%d threshold=%lu type=%d copy=%d deallocate=%d size=%u mixed=%d result=0x%x expected=0x%x\n", wide, (unsigned long)msg_ool_size_small, type, copy, dealloc, size, mixed, result, expected);
    CHECK(result == expected);
    if (expected != MACH_MSG_SUCCESS) {
        CHECK(cleaned == 1 && !allocations && !copies && !mappings);
        return;
    }
    CHECK(!cleaned);
    CHECK(allocations == ((size || mixed) && copy == MACH_MSG_PHYSICAL_COPY && !dealloc && msg_ool_size_small == 0));
    CHECK(copies == allocations);
    CHECK(mappings == !!(size || mixed));
    mach_msg_descriptor_t *d = (void *)((mach_msg_base_t *)kmsg.ikm_header + 1);
    for (unsigned int i = 0; i < (mixed ? 3u : 1u); ++i) {
        unsigned int length = mixed && i == 1 ? 5 : size;
        mach_msg_ool_descriptor_t *ool = (void *)&d[i];
        CHECK(ool->size == length);
        CHECK((ool->address == NULL) == (length == 0));
        CHECK(ool->type == type);
        CHECK(ool->copy == copy);
        CHECK(ool->deallocate == dealloc);
    }
    if (copies) CHECK(memcmp(storage, "hello", 5) == 0);
}
int main(void) {
    for (int wide = 0; wide <= 1; ++wide)
    for (int small = 0; small <= 1; ++small) {
        msg_ool_size_small = small ? 8192 : 0;
        for (int type = MACH_MSG_OOL_DESCRIPTOR; type <= MACH_MSG_OOL_VOLATILE_DESCRIPTOR; ++type) {
            if (type != MACH_MSG_OOL_DESCRIPTOR && type != MACH_MSG_OOL_VOLATILE_DESCRIPTOR) continue;
            for (int copy = MACH_MSG_PHYSICAL_COPY; copy <= MACH_MSG_VIRTUAL_COPY; ++copy)
            for (int dealloc = 0; dealloc <= 1; ++dealloc) {
                run(wide, type, copy, dealloc, 0, 0, 0, MACH_MSG_SUCCESS);
                run(wide, type, copy, dealloc, 0x1000, 0, 0, MACH_MSG_SUCCESS);
                run(wide, type, copy, dealloc, ~0ULL, 0, 0, MACH_MSG_SUCCESS);
                run(wide, type, copy, dealloc, 0x1000, 5, 0, MACH_MSG_SUCCESS);
                run(wide, type, copy, dealloc, 0, 0, 1, MACH_MSG_SUCCESS);
            }
            run(wide, type, 255, 0, 0, 0, 0, MACH_SEND_INVALID_TYPE);
        }
        run(wide, MACH_MSG_OOL_DESCRIPTOR, MACH_MSG_PHYSICAL_COPY, 0, 0x1000, 16385, 0, MACH_MSG_VM_KERNEL);
    }
    puts("PASS production OOL copyin/body: 32/64-bit wire layouts, zero/nonzero threshold, empty NULL/valid/invalid addresses, copy modes, deallocate, volatile, mixed payload, invalid option, VM limit");
    return 0;
}
