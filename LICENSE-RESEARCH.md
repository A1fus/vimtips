# Vim and Neovim help-index licensing

## Summary

`vimtip` reads each editor's installed `doc/index.txt`; it does not bundle those
files. It extracts help tags, keys, and descriptions, including continuation
text, and prints a description with the editor name and `:help` tag. The official
sources reviewed here do not specifically determine whether those extracted
strings can be redistributed without license obligations. This is a preliminary
source review, not legal advice.

## Relevant sources

- Vim distinguishes its source-code license from its documentation license.
  The [Vim license](https://github.com/vim/vim/blob/master/LICENSE#L3-L14)
  covers Vim source code and sets conditions for redistribution. Vim's
  [`uganda.txt`](https://github.com/vim/vim/blob/master/runtime/doc/uganda.txt#L31-L34)
  says the documentation is under the Open Publication License (OPL), and
  [identifies the manual's copyright and OPL version](https://github.com/vim/vim/blob/master/runtime/doc/uganda.txt#L151-L153).
  Vim's [user manual](https://github.com/vim/vim/blob/master/runtime/doc/usr_01.txt#L170-L179)
  likewise states its documentation license. The OPL URL cited in Vim's
  documentation was unavailable during this review, so its detailed terms were
  not verified.
- The [Vim index](https://github.com/vim/vim/blob/master/runtime/doc/index.txt#L1-L9)
  describes itself as a list of commands, tags, and short descriptions. The
  [Neovim index](https://github.com/neovim/neovim/blob/master/runtime/doc/index.txt#L1-L10)
  describes a similar list.
- Neovim's [license](https://github.com/neovim/neovim/blob/master/LICENSE.txt#L1-L4)
  says Apache License 2.0 applies except to parts contributed under the Vim
  license. Its [Apache license text](https://github.com/neovim/neovim/blob/master/LICENSE.txt#L97-L129)
  sets conditions for redistribution of Apache-licensed works, while its
  [README](https://github.com/neovim/neovim/blob/master/README.md#L97-L99)
  explains that Vim-patch contributions are identified. These sources do not
  establish the complete licensing provenance of every entry in the index.
- In this project, [`load_indexes`](vimtip.py) reads the installed indexes;
  [`parse_index`](vimtip.py) extracts tags, keys, and descriptions; and the
  output prints the description, editor attribution, and help tag.

## Practical implications

- Reading a copy already installed by the user is different from shipping a
  copy of the index, but that distinction alone does not settle the licensing
  status of descriptions the application displays.
- The project's MIT license covers the project's own work; it should not be
  presented as relicensing Vim or Neovim documentation.
- Outputting only a help tag or command name is narrower than reproducing the
  accompanying description. Avoid bundling or caching index text unless its
  applicable terms have been checked.
- The current `Documented by` output is useful attribution, but the reviewed
  sources do not establish that it satisfies every applicable notice or
  attribution condition.

For a release decision that depends on redistribution rights, have counsel
review the applicable documentation terms and the specific text reproduced.
