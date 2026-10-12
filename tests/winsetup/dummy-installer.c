/* Stand-in for mini_installer.exe used to test the setup window: sleeps, then exits 0
   (or with the code given as the first argument, e.g. `--exit=7`). */
#include <windows.h>
int WINAPI wWinMain(HINSTANCE a, HINSTANCE b, PWSTR cmd, int show) {
  Sleep(9000);
  for (; *cmd; ++cmd) {
    if (cmd[0] == L'-' && cmd[1] == L'-' && cmd[2] == L'e' && cmd[3] == L'x' && cmd[4] == L'i' && cmd[5] == L't' && cmd[6] == L'=')
      return cmd[7] - L'0';
  }
  return 0;
}
