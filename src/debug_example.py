import torch
import triton
import triton.language as tl

@triton.jit
def add_kernel(
    c_ptr,
    a_ptr,
    b_ptr,
    n_elements,
    BLOCK_SIZE: tl.constexpr,
):
    """
    一个简单的 Triton 内核，用于向量加法。
    我们故意在这里埋下了一个 bug。
    """
    # 1. 获取当前程序实例的 ID
    pid = tl.program_id(axis=0)  # 只有一个轴

    # 2. 计算当前程序实例要处理的数据块的偏移量
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)

    # 3. 创建一个掩码，防止处理越界元素
    mask = offsets < n_elements

    # 4. 从输入指针加载数据块
    a = tl.load(a_ptr + offsets, mask=mask)
    b = tl.load(b_ptr + offsets, mask=mask)

    # 5. BUG 在这里！本应是 a + b，我们错误地加了 1
    output = a + b + 1

    # 6. 将结果写回输出指针
    tl.store(c_ptr + offsets, output, mask=mask)


def add(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """
    启动 add_kernel 的封装函数
    """
    c = torch.empty_like(a)
    assert a.is_cuda and b.is_cuda and c.is_cuda
    n_elements = a.numel()

    # 设置 grid
    grid = lambda meta: (triton.cdiv(n_elements, meta['BLOCK_SIZE']),)
    
    # 启动内核
    add_kernel[grid](
        c_ptr=c,
        a_ptr=a,
        b_ptr=b,
        n_elements=n_elements,
        BLOCK_SIZE=1024,
    )
    return c

if __name__ == "__main__":
    # 准备数据
    a = torch.randn((128,), device='cuda', dtype=torch.float32)
    b = torch.randn((128,), device='cuda', dtype=torch.float32)

    # 调用我们的 Triton 函数
    c_triton = add(a, b)
    
    # 正确的参考答案
    c_correct = a + b

    # 比较结果
    print("Triton 内核的输出:", c_triton)
    print("正确的 PyTorch 输出:", c_correct)
    
    # 检查是否有错误
    if not torch.allclose(c_triton, c_correct):
        print("\n[!] 结果不匹配！代码中存在 Bug！")
    else:
        print("\n[✓] 结果正确！")