#import sys
#sys.path.insert(0,'/home/erick/git/delinker/Delinker/src')
from elfmanip.elfmanip import ELFManip, CustomSection, CustomSegment
from elfmanip.constants import PT_LOAD, SHF_TLS, PT_TLS, SHF_WRITE, SHF_ALLOC

from elftools.elf.elffile import ELFFile

tls_section_added = False
tls_section_contents = b''
tls_section_offset = 0

def add_tls_section(fname,contents):
    # This does not require ELFManip because it must
    # be called earlier on, before we actually rewrite the
    # binary, because I need the new TLS offset.
    # We could obviously create the ELFManip object now, 
    # but it won't be used again until we write it out at
    # the end.
    global tls_section_added
    global tls_section_contents
    tls_section_added = True
    #Pad contents to 4-byte alignment
    with open(fname) as f:
        elf = ELFFile(f)
       	for s in elf.iter_segments():
            #Assume only one TLS segment exists (will fail on an already modified binary)
            if s.header['p_type'] == 'PT_TLS':
                tls_section_offset = s.header['p_memsz']+len(tls_section_contents)
                print 'old section is 0x%x (%x with padding)'%(s.header['p_memsz'], s.header['p_memsz']+(4-s.header['p_memsz']%4))
                print 'new content is 0x%x (%x with padding)'%(len(contents), len(contents)+(4-len(contents)%4))
                print 'overall        0x%x (%x with padding)'%(tls_section_offset, tls_section_offset+(4-tls_section_offset%4))
                return tls_section_offset + (4-tls_section_offset%4)
    return len(contents) + (4-len(contents)%4) #If there is no TLS segment

def get_tls_content(elf):
    # For now assume that the TLS sections are adjacent and
    # we can append their contents directly
    # I also am assuming that there will probably be only
    # two sections, .tdata and .tbss, which seems likely.
    # This may work under different circumstances but it is
    # hard to predict.
    content = b''
    if tls_section_added:
        content+=tls_section_contents
    print 'length of new contents: 0x%x'%len(content)
    for entry in elf.shdrs['entries']:
        if (entry.sh_flags & SHF_TLS) == SHF_TLS:
            if entry.sh_type == SHT_NOBITS: # bss has no contents
                content+='\0'*entry.sh_size # fill bss space with 0
                print 'adding .tbss section of length: 0x%x'%entry.sh_size
            else:
                content+=entry.contents
                print 'adding .tdata section of length: 0x%x'%len(entry.contents)
    return content

def rewrite_noglobal(fname,nname,newcode,newbase,entry):
  elf = ELFManip(fname,num_adtl_segments=1)
  with open(newcode) as f:
    newbytes = f.read()
    elf.relocate_phdrs()
    newtext_section = CustomSection(newbytes, sh_addr = newbase)
    if newtext_section is None:
      raise Exception
    newtext_segment = CustomSegment(PT_LOAD)
    newtext_segment = elf.add_segment(newtext_segment)
    elf.add_section(newtext_section, newtext_segment)
    elf.set_entry_point(entry)
    elf.write_new_elf(nname)

def rewrite(fname,nname,newcode,newbase,newglobal,newglobalbase,entry):
  elf = ELFManip(fname,num_adtl_segments=4)
  newtls = get_tls_content(elf) #Right now there will ALWAYS be a new TLS section
  with open(newcode) as f:
    newbytes = f.read()
    elf.relocate_phdrs()
    newtext_section = CustomSection(newbytes, sh_addr = newbase)
    newglobal_section = CustomSection(newglobal, sh_addr = newglobalbase)
    newtls_section = CustomSection(newtls, sh_addr = newglobalbase-0x10000) #TODO: make this address flexible
    newshadow_section = CustomSection('\0'*0x40000, sh_addr = 0xfefdd000, sh_flags=SHF_WRITE | SHF_ALLOC ) #Manually calculated offset from fixed stack location
    if newtext_section is None or newglobal_section is None:
      raise Exception
    newtext_segment = CustomSegment(PT_LOAD)
    newtext_segment = elf.add_segment(newtext_segment)
    newglobal_segment = CustomSegment(PT_LOAD)
    newglobal_segment = elf.add_segment(newglobal_segment)
    newshadow_segment = CustomSegment(PT_LOAD)
    newshadow_segment = elf.add_segment(newshadow_segment)
    elf.add_section(newtext_section, newtext_segment)
    elf.add_section(newglobal_section, newglobal_segment)
    elf.add_section(newshadow_section, newshadow_segment)
    
    newtls_segment = CustomSegment(PT_LOAD)
    newtls_segment = elf.add_segment(newtls_segment)
    elf.add_section(newtls_section, newtls_segment)
    newtls_segment = CustomSegment(PT_TLS, p_align=4)
    newtls_segment = elf.add_segment(newtls_segment)
    elf.add_section(newtls_section, newtls_segment)

    elf.set_entry_point(entry)
    elf.write_new_elf(nname)

if __name__ == '__main__':
  if len(sys.argv) != 2:
    print "needs filename"

  fn = sys.argv[1]

  elf = ELFManip(fn)

  newcode = 'newbytes'

  elf.add_section(newcode, sh_addr = 0x09000000)
  #elf.set_entry_point(0x09000200) #teeny
  #elf.set_entry_point(0x09000854) #simplest main
  #elf.set_entry_point(0x09000230) #eip
  #elf.set_entry_point(0x09000228) #mem
  #elf.set_entry_point(0x09002278) #64-bit echo (which therefore wouldn't work regardless)
  #elf.set_entry_point(0x09000765) #simplest (_init at 0xc78)
  #elf.set_entry_point(0x0900026c) #lookup
  #(0x8048cf0 - 0x8048000)+0x59838 = 0x5a428 (lookup index)
  #elf.set_entry_point(0x09001ce8) #bzip2
  elf.set_entry_point(0x090013ef) #ssimplest

  elf.write_new_elf('relocated')

